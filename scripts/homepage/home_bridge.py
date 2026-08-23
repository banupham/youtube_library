#!/usr/bin/env python3
"""Local bridge for read-only YouTube recommendation collection.

Home and Up Next observations are stored separately as raw evidence, but each
collection session produces one consolidated profile report and one current
profile-library record.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
}

CONTEXT_FIELDS = (
    "collection_session_id",
    "extraction_mode",
    "parent_video_id",
    "parent_title",
    "parent_channel",
    "parent_home_position",
    "source_home_captured_at",
    "sample_context",
    "replay_context",
    "page_url",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--no-classify", action="store_true")
    return parser.parse_args()


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
    payload["surface_context"] = {key: source_payload.get(key) for key in CONTEXT_FIELDS if key in source_payload}
    write_json(path, payload)


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    profile_root = repo_root / "data" / "profile_reports"
    library_root = repo_root / "data" / "profile_library"
    session_root = repo_root / "data" / "collection_sessions"
    classifier = repo_root / "scripts" / "classification" / "classify_homepage_v2.py"
    enricher = repo_root / "scripts" / "enrichment" / "youtube_enrich.py"
    consolidated_builder = repo_root / "scripts" / "profile" / "build_consolidated_profile.py"

    roots = [profile_root, library_root, session_root]
    for config in SURFACES.values():
        roots.extend(repo_root / "data" / config[key] for key in ("snapshot_dir", "enriched_dir", "classified_dir"))
    for folder in roots:
        folder.mkdir(parents=True, exist_ok=True)

    index_lock = threading.Lock()

    def session_index_path(profile: dict, session_id: str) -> Path:
        return session_root / f"profile_{profile['profile_short_id']}__{safe_token(session_id, 64)}.json"

    def update_session_index(profile: dict, session_id: str, source: str, entry: dict) -> Path:
        path = session_index_path(profile, session_id)
        with index_lock:
            if path.exists():
                session = json.loads(path.read_text(encoding="utf-8"))
            else:
                session = {
                    "collection_session_id": session_id,
                    "profile": profile,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "surfaces": {"home": [], "up_next": []},
                }
            session["profile"] = profile
            session["updated_at"] = datetime.now(timezone.utc).isoformat()
            key = SURFACES[source]["key"]
            session.setdefault("surfaces", {}).setdefault(key, []).append(entry)
            write_json(path, session)
        return path

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryBridge/0.7"

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json_response(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/collect":
                self._handle_collect()
                return
            if self.path == "/finalize":
                self._handle_finalize()
                return
            self._json_response(404, {"error": "not_found"})

        def _read_payload(self) -> dict | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception as exc:
                self._json_response(400, {"error": "invalid_json", "detail": str(exc)})
                return None

        def _handle_collect(self) -> None:
            payload = self._read_payload()
            if payload is None:
                return
            source = payload.get("source")
            config = SURFACES.get(source)
            items = payload.get("items")
            if not config or not isinstance(items, list):
                self._json_response(400, {"error": "invalid_snapshot_schema", "allowed_sources": sorted(SURFACES)})
                return
            if source == "youtube_up_next" and not payload.get("parent_video_id"):
                self._json_response(400, {"error": "missing_parent_video_id"})
                return

            profile = normalize_profile(payload.get("collector_profile"))
            payload["collector_profile"] = profile
            session_id = str(payload.get("collection_session_id") or "").strip()
            if not session_id:
                self._json_response(400, {"error": "missing_collection_session_id"})
                return

            profile_folder = f"profile_{profile['profile_short_id']}"
            snapshot_dir = repo_root / "data" / config["snapshot_dir"] / profile_folder
            enriched_dir = repo_root / "data" / config["enriched_dir"] / profile_folder
            classified_dir = repo_root / "data" / config["classified_dir"] / profile_folder
            for folder in (snapshot_dir, enriched_dir, classified_dir):
                folder.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
            if source == "youtube_home":
                base = f"home_{timestamp}"
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
            if not args.no_enrich and os.environ.get("YOUTUBE_API_KEY") and items:
                try:
                    run_command([sys.executable, str(enricher), str(snapshot_path), "--output", str(enriched_path)], repo_root)
                    classification_input = enriched_path
                    enrichment_status = "ok"
                except subprocess.CalledProcessError as exc:
                    enrichment_status = f"failed:{exc.returncode}"
                    print(f"Warning: {config['label']} API enrichment failed; using surface-visible data.")

            classified_value = None
            if not args.no_classify:
                try:
                    run_command([sys.executable, str(classifier), str(classification_input), "--output", str(classified_path)], repo_root)
                    inject_context(classified_path, profile, payload)
                    classified_value = str(classified_path.relative_to(repo_root))
                except subprocess.CalledProcessError as exc:
                    self._json_response(500, {
                        "error": "classification_failed",
                        "source": source,
                        "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                        "returncode": exc.returncode,
                    })
                    return

            entry = {
                "source": source,
                "classified_path": classified_value,
                "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                "item_count": len(items),
                "captured_at": payload.get("captured_at"),
            }
            for key in ("parent_video_id", "parent_title", "parent_home_position", "sample_context", "replay_context"):
                if key in payload:
                    entry[key] = payload.get(key)
            index_path = update_session_index(profile, session_id, source, entry)

            print(
                f"[{profile['profile_label']}:{profile['profile_short_id']}] {config['label']} "
                f"{len(items)} items -> {snapshot_path.relative_to(repo_root)}"
            )
            self._json_response(200, {
                "ok": True,
                "source": source,
                "surface": config["key"],
                "profile_id": profile["profile_id"],
                "profile_short_id": profile["profile_short_id"],
                "profile_label": profile["profile_label"],
                "collection_session_id": session_id,
                "item_count": len(items),
                "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                "classified_path": classified_value,
                "enrichment": enrichment_status,
                "session_index_path": str(index_path.relative_to(repo_root)),
                "profile_report_status": "deferred_to_session_finalize",
            })

        def _handle_finalize(self) -> None:
            payload = self._read_payload()
            if payload is None:
                return
            profile = normalize_profile(payload.get("collector_profile"))
            session_id = str(payload.get("collection_session_id") or "").strip()
            if not session_id:
                self._json_response(400, {"error": "missing_collection_session_id"})
                return
            index_path = session_index_path(profile, session_id)
            if not index_path.exists():
                self._json_response(404, {"error": "session_not_found", "collection_session_id": session_id})
                return

            short_id = profile["profile_short_id"]
            current_json = profile_root / f"profile_{short_id}__current.profile.json"
            current_html = profile_root / f"profile_{short_id}__current.profile.html"
            library_json = library_root / f"profile_{short_id}.json"
            history_jsonl = library_root / f"profile_{short_id}.history.jsonl"

            try:
                run_command([
                    sys.executable,
                    str(consolidated_builder),
                    str(index_path),
                    "--json-output", str(current_json),
                    "--html-output", str(current_html),
                    "--library-output", str(library_json),
                    "--history-output", str(history_jsonl),
                ], repo_root)
            except subprocess.CalledProcessError as exc:
                self._json_response(500, {"error": "consolidated_profile_failed", "returncode": exc.returncode})
                return

            try:
                current_profile = json.loads(current_json.read_text(encoding="utf-8"))
                behavior_name = current_profile.get("behavior_profile_name")
            except Exception:
                behavior_name = None

            self._json_response(200, {
                "ok": True,
                "profile_id": profile["profile_id"],
                "profile_short_id": short_id,
                "profile_label": profile["profile_label"],
                "collection_session_id": session_id,
                "behavior_profile_name": behavior_name,
                "profile_json_path": str(current_json.relative_to(repo_root)),
                "profile_html_path": str(current_html.relative_to(repo_root)),
                "library_path": str(library_json.relative_to(repo_root)),
                "history_path": str(history_jsonl.relative_to(repo_root)),
            })

        def log_message(self, format: str, *values: object) -> None:
            print(f"[bridge] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Recommendation Bridge v0.7: http://{args.host}:{args.port}")
    print("Surfaces: Home + Up Next replay")
    print("Reports: one consolidated current profile per browser profile")
    print("Profile library: data/profile_library")
    print("Visual report: data/profile_reports/profile_<id>__current.profile.html")
    print("Up Next collection is HTML-only; no navigation/player/playback")
    if os.environ.get("YOUTUBE_API_KEY"):
        print("YouTube API enrichment: ENABLED")
    else:
        print("YouTube API enrichment: disabled (set YOUTUBE_API_KEY to enable)")
    print("Giữ terminal mở và dùng extension trên YouTube Home. Ctrl+C để dừng.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Bridge stopped.")


if __name__ == "__main__":
    main()
