#!/usr/bin/env python3
"""In-process Chrome recommendation/profile analysis pipeline.

No HTTP server is opened here. The canonical community server imports this
module and calls collect()/finalize() directly.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

SURFACES = {
    "youtube_home": {
        "key": "home",
        "label": "Home",
        "snapshot_dir": "home_snapshots",
        "enriched_dir": "home_enriched",
        "classified_dir": "home_classified",
    },
    "youtube_up_next": {
        "key": "up_next",
        "label": "Up Next",
        "snapshot_dir": "up_next_snapshots",
        "enriched_dir": "up_next_enriched",
        "classified_dir": "up_next_classified",
    },
    "youtube_subscriptions": {
        "key": "subscriptions",
        "label": "Subscriptions",
        "snapshot_dir": "subscriptions_snapshots",
        "enriched_dir": "subscriptions_enriched",
        "classified_dir": "subscriptions_classified",
    },
}

CONTEXT_FIELDS = (
    "collection_session_id",
    "extraction_mode",
    "extraction_version",
    "extraction_diagnostics",
    "parent_video_id",
    "parent_title",
    "parent_channel",
    "parent_home_position",
    "source_home_captured_at",
    "sample_context",
    "replay_context",
    "subscription_channels",
    "page_url",
)


def run_command(command: list[str], repo_root: Path) -> None:
    subprocess.run(command, cwd=str(repo_root), check=True)


def profile_short_id(profile_id: object) -> str:
    value = str(profile_id or "").strip()
    if value.startswith("browser-"):
        value = value[len("browser-"):]
    value = re.sub(r"[^A-Za-z0-9]", "", value)
    return value[:8] or "legacy"


def normalize_profile(raw: object) -> dict:
    profile = raw if isinstance(raw, dict) else {}
    profile_id = str(profile.get("profile_id") or "legacy-unidentified").strip()
    short_id = profile_short_id(profile_id)
    label = str(profile.get("profile_label") or f"Profile {short_id}").strip()[:60]
    return {
        "profile_id": profile_id,
        "profile_label": label,
        "profile_short_id": short_id,
        "identity_source": str(profile.get("identity_source") or "legacy_or_unknown"),
    }


def safe_token(value: object, limit: int = 48) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))
    return token[:limit] or "unknown"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inject_context(path: Path, profile: dict, source_payload: dict) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["collector_profile"] = profile
    for key in CONTEXT_FIELDS:
        if key in source_payload:
            payload[key] = source_payload.get(key)
    payload["surface_context"] = {
        key: source_payload.get(key)
        for key in CONTEXT_FIELDS
        if key in source_payload
    }
    write_json(path, payload)


class BrowserPipeline:
    def __init__(self, repo_root: Path, *, no_enrich: bool = False, no_classify: bool = False):
        self.repo_root = Path(repo_root)
        self.no_enrich = no_enrich
        self.no_classify = no_classify
        self.profile_root = self.repo_root / "data" / "profile_reports"
        self.library_root = self.repo_root / "data" / "profile_library"
        self.session_root = self.repo_root / "data" / "collection_sessions"
        self.classifier = self.repo_root / "scripts" / "classification" / "classify_homepage_v2.py"
        self.enricher = self.repo_root / "scripts" / "enrichment" / "youtube_enrich.py"
        self.consolidated_builder = self.repo_root / "scripts" / "profile" / "build_consolidated_profile.py"
        self.temporal_builder = self.repo_root / "scripts" / "profile" / "build_temporal_profile.py"
        self.index_lock = threading.RLock()

        roots = [self.profile_root, self.library_root, self.session_root]
        for config in SURFACES.values():
            roots.extend(
                self.repo_root / "data" / config[key]
                for key in ("snapshot_dir", "enriched_dir", "classified_dir")
            )
        for folder in roots:
            folder.mkdir(parents=True, exist_ok=True)

    def session_index_path(self, profile: dict, session_id: str) -> Path:
        return self.session_root / f"profile_{profile['profile_short_id']}__{safe_token(session_id, 64)}.json"

    def update_session_index(self, profile: dict, session_id: str, source: str, entry: dict) -> Path:
        path = self.session_index_path(profile, session_id)
        with self.index_lock:
            if path.exists():
                session = json.loads(path.read_text(encoding="utf-8"))
            else:
                session = {
                    "collection_session_id": session_id,
                    "profile": profile,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "surfaces": {"home": [], "up_next": [], "subscriptions": []},
                }
            session["profile"] = profile
            session["updated_at"] = datetime.now(timezone.utc).isoformat()
            key = SURFACES[source]["key"]
            session.setdefault("surfaces", {}).setdefault(key, []).append(entry)
            write_json(path, session)
        return path

    def update_library_index(self, profile: dict, current_profile: dict, report_path: Path, library_path: Path) -> Path:
        path = self.library_root / "index.json"
        with self.index_lock:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = {"version": "1.1.0", "profiles": []}
            profiles = [
                row
                for row in payload.get("profiles", [])
                if row.get("profile_id") != profile["profile_id"]
            ]
            interests = current_profile.get("interest_weights") or []
            temporal = current_profile.get("temporal_profile") or {}
            profiles.append(
                {
                    "profile_id": profile["profile_id"],
                    "profile_short_id": profile["profile_short_id"],
                    "profile_label": profile["profile_label"],
                    "behavior_profile_name": current_profile.get("behavior_profile_name"),
                    "certainty_score": current_profile.get("certainty_score"),
                    "daily_observation_count": temporal.get("daily_observation_count"),
                    "top_interests": [
                        {
                            "id": row.get("id"),
                            "name_vi": row.get("name_vi"),
                            "weight": row.get("predicted_weight"),
                            "trend_state": row.get("trend_state"),
                        }
                        for row in interests[:4]
                    ],
                    "updated_at": current_profile.get("updated_at"),
                    "report_path": str(report_path.relative_to(self.repo_root)),
                    "library_path": str(library_path.relative_to(self.repo_root)),
                }
            )
            profiles.sort(key=lambda row: str(row.get("profile_label") or row.get("profile_short_id") or ""))
            payload["profiles"] = profiles
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_json(path, payload)
        return path

    def collect(self, payload: object) -> tuple[int, dict]:
        if not isinstance(payload, dict):
            return 400, {"error": "invalid_snapshot_schema"}
        source = str(payload.get("source") or "")
        config = SURFACES.get(source)
        items = payload.get("items")
        if not config or not isinstance(items, list):
            return 400, {"error": "invalid_snapshot_schema", "allowed_sources": sorted(SURFACES)}
        if source == "youtube_up_next" and not payload.get("parent_video_id"):
            return 400, {"error": "missing_parent_video_id"}

        profile = normalize_profile(payload.get("collector_profile"))
        payload["collector_profile"] = profile
        session_id = str(payload.get("collection_session_id") or "").strip()
        if not session_id:
            return 400, {"error": "missing_collection_session_id"}

        profile_folder = f"profile_{profile['profile_short_id']}"
        snapshot_dir = self.repo_root / "data" / config["snapshot_dir"] / profile_folder
        enriched_dir = self.repo_root / "data" / config["enriched_dir"] / profile_folder
        classified_dir = self.repo_root / "data" / config["classified_dir"] / profile_folder
        for folder in (snapshot_dir, enriched_dir, classified_dir):
            folder.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        if source == "youtube_home":
            base = f"home_{timestamp}"
        elif source == "youtube_subscriptions":
            base = f"subscriptions_{timestamp}"
        else:
            parent = safe_token(payload.get("parent_video_id"), 16)
            replay = payload.get("replay_context") if isinstance(payload.get("replay_context"), dict) else {}
            try:
                replay_index = int(replay.get("replay_index") or 0)
            except (TypeError, ValueError):
                replay_index = 0
            replay_token = f"_r{replay_index:02d}" if replay_index else ""
            base = f"upnext_{parent}{replay_token}_{timestamp}"

        snapshot_path = snapshot_dir / f"{base}.json"
        enriched_path = enriched_dir / f"{base}.json"
        classified_path = classified_dir / f"{base}.json"
        write_json(snapshot_path, payload)

        classification_input = snapshot_path
        enrichment_status = "skipped"
        if not self.no_enrich and os.environ.get("YOUTUBE_API_KEY") and items:
            try:
                run_command(
                    [sys.executable, str(self.enricher), str(snapshot_path), "--output", str(enriched_path)],
                    self.repo_root,
                )
                classification_input = enriched_path
                enrichment_status = "ok"
            except subprocess.CalledProcessError as exc:
                enrichment_status = f"failed:{exc.returncode}"
                print(f"Warning: {config['label']} API enrichment failed; using surface-visible data.")

        classified_value = None
        if not self.no_classify and items:
            try:
                run_command(
                    [sys.executable, str(self.classifier), str(classification_input), "--output", str(classified_path)],
                    self.repo_root,
                )
                inject_context(classified_path, profile, payload)
                classified_value = str(classified_path.relative_to(self.repo_root))
            except subprocess.CalledProcessError as exc:
                return 500, {
                    "error": "classification_failed",
                    "source": source,
                    "snapshot_path": str(snapshot_path.relative_to(self.repo_root)),
                    "returncode": exc.returncode,
                }

        entry = {
            "source": source,
            "classified_path": classified_value,
            "snapshot_path": str(snapshot_path.relative_to(self.repo_root)),
            "item_count": len(items),
            "captured_at": payload.get("captured_at"),
        }
        for key in (
            "parent_video_id",
            "parent_title",
            "parent_home_position",
            "sample_context",
            "replay_context",
            "extraction_version",
        ):
            if key in payload:
                entry[key] = payload.get(key)
        if source == "youtube_subscriptions":
            entry["subscription_channel_count"] = len(payload.get("subscription_channels") or [])
        index_path = self.update_session_index(profile, session_id, source, entry)

        print(f"[{profile['profile_label']}:{profile['profile_short_id']}] {config['label']} {len(items)} items")
        return 200, {
            "ok": True,
            "source": source,
            "surface": config["key"],
            "profile_id": profile["profile_id"],
            "profile_short_id": profile["profile_short_id"],
            "profile_label": profile["profile_label"],
            "collection_session_id": session_id,
            "item_count": len(items),
            "subscription_channel_count": len(payload.get("subscription_channels") or []) if source == "youtube_subscriptions" else None,
            "snapshot_path": str(snapshot_path.relative_to(self.repo_root)),
            "classified_path": classified_value,
            "enrichment": enrichment_status,
            "session_index_path": str(index_path.relative_to(self.repo_root)),
            "profile_report_status": "deferred_to_session_finalize",
        }

    def finalize(self, payload: object) -> tuple[int, dict]:
        if not isinstance(payload, dict):
            return 400, {"error": "invalid_payload"}
        profile = normalize_profile(payload.get("collector_profile"))
        session_id = str(payload.get("collection_session_id") or "").strip()
        if not session_id:
            return 400, {"error": "missing_collection_session_id"}
        index_path = self.session_index_path(profile, session_id)
        if not index_path.exists():
            return 404, {"error": "session_not_found", "collection_session_id": session_id}

        short_id = profile["profile_short_id"]
        current_json = self.profile_root / f"profile_{short_id}__current.profile.json"
        current_html = self.profile_root / f"profile_{short_id}__current.profile.html"
        library_json = self.library_root / f"profile_{short_id}.json"
        history_jsonl = self.library_root / f"profile_{short_id}.history.jsonl"
        daily_dir = self.library_root / "daily" / f"profile_{short_id}"

        token = safe_token(session_id, 64)
        session_profile_json = self.session_root / f"profile_{short_id}__{token}.session.profile.json"
        session_profile_html = self.session_root / f"profile_{short_id}__{token}.session.profile.html"

        try:
            run_command(
                [
                    sys.executable,
                    str(self.consolidated_builder),
                    str(index_path),
                    "--json-output",
                    str(session_profile_json),
                    "--html-output",
                    str(session_profile_html),
                    "--library-output",
                    str(session_profile_json),
                ],
                self.repo_root,
            )
        except subprocess.CalledProcessError as exc:
            return 500, {"error": "session_profile_failed", "returncode": exc.returncode}

        temporal_command = [
            sys.executable,
            str(self.temporal_builder),
            str(session_profile_json),
            str(index_path),
            "--json-output",
            str(current_json),
            "--html-output",
            str(current_html),
            "--library-output",
            str(library_json),
            "--history-output",
            str(history_jsonl),
            "--daily-dir",
            str(daily_dir),
        ]
        if library_json.exists():
            temporal_command.extend(["--previous-profile", str(library_json)])

        try:
            run_command(temporal_command, self.repo_root)
        except subprocess.CalledProcessError as exc:
            return 500, {"error": "temporal_profile_failed", "returncode": exc.returncode}

        for temporary in (session_profile_json, session_profile_html):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

        library_index = None
        try:
            current_profile = json.loads(current_json.read_text(encoding="utf-8"))
            behavior_name = current_profile.get("behavior_profile_name")
            temporal = current_profile.get("temporal_profile") or {}
            library_index = self.update_library_index(profile, current_profile, current_html, library_json)
        except Exception as exc:
            behavior_name = None
            temporal = {}
            print(f"Warning: profile library index update failed: {exc}")

        return 200, {
            "ok": True,
            "profile_id": profile["profile_id"],
            "profile_short_id": short_id,
            "profile_label": profile["profile_label"],
            "collection_session_id": session_id,
            "behavior_profile_name": behavior_name,
            "daily_observation_count": temporal.get("daily_observation_count"),
            "profile_json_path": str(current_json.relative_to(self.repo_root)),
            "profile_html_path": str(current_html.relative_to(self.repo_root)),
            "library_path": str(library_json.relative_to(self.repo_root)),
            "library_index_path": str(library_index.relative_to(self.repo_root)) if library_index else None,
            "history_path": str(history_jsonl.relative_to(self.repo_root)),
            "daily_path": str(daily_dir.relative_to(self.repo_root)),
            "profile_url": f"/profile/{short_id}",
            "dashboard_url": "/",
        }
