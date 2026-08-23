#!/usr/bin/env python3
"""Natural interaction storage for Chrome and Android collectors.

Collectors compute the v1 score locally. The central server validates and stores
raw event evidence, then maintains machine-readable daily + rolling 7d/30d
summaries. Comment contents are never accepted or stored.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ALLOWED_EVENTS = {
    "video_open",
    "like",
    "unlike",
    "dislike",
    "undislike",
    "comment_submit",
}
ALLOWED_PLATFORMS = {"browser", "android"}
ALLOWED_SUB_STATES = {"subscribed", "not_subscribed", "unknown"}
SCORE_MODEL = "natural_interaction_v1"


def safe_short(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_interaction(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors: list[str] = []
    required = (
        "schema_version",
        "event_id",
        "participant_id",
        "device_id",
        "profile_id",
        "platform",
        "captured_at",
        "event_type",
        "engagement_score",
        "score_model",
        "source",
    )
    for key in required:
        if key not in payload:
            errors.append(f"missing {key}")
    if payload.get("schema_version") != "1.0.0":
        errors.append("unsupported schema_version")
    if str(payload.get("score_model") or "") != SCORE_MODEL:
        errors.append("unsupported score_model")
    if str(payload.get("source") or "") != "natural_user_action":
        errors.append("invalid source")
    if str(payload.get("platform") or "") not in ALLOWED_PLATFORMS:
        errors.append("invalid platform")
    if str(payload.get("event_type") or "") not in ALLOWED_EVENTS:
        errors.append("invalid event_type")
    if str(payload.get("channel_subscription_state") or "unknown") not in ALLOWED_SUB_STATES:
        errors.append("invalid channel_subscription_state")
    for key, min_len, max_len in (
        ("event_id", 8, 120),
        ("participant_id", 4, 200),
        ("device_id", 4, 200),
        ("profile_id", 1, 200),
    ):
        value = str(payload.get(key) or "")
        if not min_len <= len(value) <= max_len:
            errors.append(f"invalid {key}")
    captured_at = str(payload.get("captured_at") or "")
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError:
        errors.append("invalid captured_at")
    try:
        score = float(payload.get("engagement_score"))
        if not -2.0 <= score <= 2.0:
            errors.append("engagement_score outside [-2,2]")
    except (TypeError, ValueError):
        errors.append("invalid engagement_score")
    try:
        confidence = float(payload.get("confidence", 1.0))
        if not 0.0 <= confidence <= 1.0:
            errors.append("confidence outside [0,1]")
    except (TypeError, ValueError):
        errors.append("invalid confidence")

    # Comments are evidence-only in v1. Reject fields that could contain the
    # participant's comment content or typed text.
    forbidden = {"comment_text", "text", "body", "message", "typed_text", "comment_body"}
    present = forbidden.intersection(payload)
    if present:
        errors.append("comment/text content is forbidden: " + ", ".join(sorted(present)))
    context = payload.get("context")
    if context is not None and not isinstance(context, dict):
        errors.append("context must be an object")
    elif isinstance(context, dict):
        forbidden_context = forbidden.intersection(context)
        if forbidden_context:
            errors.append("comment/text content is forbidden in context")
    return errors


def sanitize_interaction(payload: dict) -> dict:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    safe_context = {
        key: context.get(key)
        for key in ("page_url", "tree_signature", "event_class", "detection")
        if key in context
    }
    return {
        "schema_version": "1.0.0",
        "event_id": str(payload["event_id"])[:120],
        "participant_id": str(payload["participant_id"])[:200],
        "device_id": str(payload["device_id"])[:200],
        "profile_id": str(payload["profile_id"])[:200],
        "profile_slot": str(payload.get("profile_slot") or "")[:120] or None,
        "platform": str(payload["platform"]),
        "captured_at": str(payload["captured_at"])[:80],
        "event_type": str(payload["event_type"]),
        "engagement_score": round(float(payload["engagement_score"]), 4),
        "score_model": SCORE_MODEL,
        "source": "natural_user_action",
        "video_id": str(payload.get("video_id") or "")[:32] or None,
        "video_title": str(payload.get("video_title") or "")[:300] or None,
        "channel": str(payload.get("channel") or "")[:240] or None,
        "channel_subscription_state": str(payload.get("channel_subscription_state") or "unknown"),
        "surface": str(payload.get("surface") or "")[:80] or None,
        "confidence": round(float(payload.get("confidence", 1.0)), 4),
        "context": safe_context,
    }


class InteractionStore:
    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.raw_root = self.repo_root / "data" / "interaction_events"
        self.daily_root = self.repo_root / "data" / "interaction_daily"
        self.index_root = self.repo_root / "data" / "interaction_profile_index"
        self.lock = threading.RLock()

    def _profile_dir(self, root: Path, payload: dict) -> Path:
        participant = safe_short(str(payload["participant_id"]), 12)
        device = safe_short(str(payload["device_id"]), 12)
        profile = safe_short(str(payload["profile_id"]), 16)
        return root / f"participant_{participant}" / f"device_{device}" / f"profile_{profile}"

    def _index_path(self, profile_id: str) -> Path:
        return self.index_root / f"profile_{safe_short(profile_id, 20)}.json"

    def _event_exists(self, path: Path, event_id: str) -> bool:
        if not path.exists():
            return False
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if event_id in line:
                        try:
                            if str(json.loads(line).get("event_id") or "") == event_id:
                                return True
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return False
        return False

    def ingest(self, payload: object) -> tuple[int, dict]:
        errors = validate_interaction(payload)
        if errors:
            return 400, {"error": "invalid_interaction", "details": errors[:20]}
        assert isinstance(payload, dict)
        event = sanitize_interaction(payload)
        day = event["captured_at"][:10]
        try:
            date.fromisoformat(day)
        except ValueError:
            return 400, {"error": "invalid_interaction_day"}

        raw_dir = self._profile_dir(self.raw_root, event)
        daily_dir = self._profile_dir(self.daily_root, event)
        raw_path = raw_dir / f"{day}.jsonl"
        daily_path = daily_dir / f"{day}.json"

        with self.lock:
            raw_dir.mkdir(parents=True, exist_ok=True)
            duplicate = self._event_exists(raw_path, event["event_id"])
            if not duplicate:
                with raw_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                self._update_daily(daily_path, event)
                self._write_index(event, daily_dir)
                rolling_7d = self._build_window(daily_dir, 7)
                rolling_30d = self._build_window(daily_dir, 30)
                write_json(daily_dir / "rolling_7d.json", rolling_7d)
                write_json(daily_dir / "rolling_30d.json", rolling_30d)
            else:
                rolling_7d = self._read_or_empty(daily_dir / "rolling_7d.json", 7)
                rolling_30d = self._read_or_empty(daily_dir / "rolling_30d.json", 30)

        return 200, {
            "ok": True,
            "duplicate": duplicate,
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "stored_day": day,
            "daily_score": self._read_daily_score(daily_path),
            "rolling_7d_score": rolling_7d.get("score_total", 0.0),
            "rolling_30d_score": rolling_30d.get("score_total", 0.0),
        }

    def _update_daily(self, path: Path, event: dict) -> None:
        if path.exists():
            try:
                daily = read_json(path)
            except (OSError, json.JSONDecodeError):
                daily = {}
        else:
            daily = {}
        counts = dict(daily.get("event_counts") or {})
        event_type = event["event_type"]
        counts[event_type] = int(counts.get(event_type, 0)) + 1
        sub_counts = dict(daily.get("video_open_subscription_counts") or {})
        if event_type == "video_open":
            state = event.get("channel_subscription_state") or "unknown"
            sub_counts[state] = int(sub_counts.get(state, 0)) + 1
        daily.update(
            {
                "schema_version": "1.0.0",
                "date": event["captured_at"][:10],
                "platform": event["platform"],
                "profile_id": event["profile_id"],
                "score_model": SCORE_MODEL,
                "event_count": int(daily.get("event_count", 0)) + 1,
                "event_counts": counts,
                "score_total": round(float(daily.get("score_total", 0.0)) + float(event["engagement_score"]), 4),
                "video_open_subscription_counts": sub_counts,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        write_json(path, daily)

    def _write_index(self, event: dict, daily_dir: Path) -> None:
        write_json(
            self._index_path(event["profile_id"]),
            {
                "schema_version": "1.0.0",
                "profile_id": event["profile_id"],
                "participant_hash": safe_short(event["participant_id"], 12),
                "device_hash": safe_short(event["device_id"], 12),
                "daily_dir": str(daily_dir.relative_to(self.repo_root)),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _build_window(self, daily_dir: Path, days: int) -> dict:
        today = date.today()
        start = today - timedelta(days=days - 1)
        counts: dict[str, int] = {}
        sub_counts: dict[str, int] = {}
        score_total = 0.0
        event_count = 0
        included_days = 0
        for path in sorted(daily_dir.glob("????-??-??.json")):
            try:
                day = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if day < start or day > today:
                continue
            try:
                row = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            included_days += 1
            event_count += int(row.get("event_count", 0))
            score_total += float(row.get("score_total", 0.0))
            for key, value in (row.get("event_counts") or {}).items():
                counts[key] = counts.get(key, 0) + int(value)
            for key, value in (row.get("video_open_subscription_counts") or {}).items():
                sub_counts[key] = sub_counts.get(key, 0) + int(value)
        return {
            "schema_version": "1.0.0",
            "window_days": days,
            "window_start": start.isoformat(),
            "window_end": today.isoformat(),
            "observed_days": included_days,
            "event_count": event_count,
            "event_counts": counts,
            "score_total": round(score_total, 4),
            "video_open_subscription_counts": sub_counts,
            "score_model": SCORE_MODEL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _read_or_empty(self, path: Path, days: int) -> dict:
        try:
            return read_json(path)
        except (OSError, json.JSONDecodeError):
            return {
                "window_days": days,
                "event_count": 0,
                "event_counts": {},
                "score_total": 0.0,
                "video_open_subscription_counts": {},
            }

    def _read_daily_score(self, path: Path) -> float:
        try:
            return float(read_json(path).get("score_total", 0.0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return 0.0

    def summary_for_profile(self, profile_id: str) -> dict | None:
        index_path = self._index_path(profile_id)
        if not index_path.exists():
            return None
        try:
            index = read_json(index_path)
            daily_dir = self.repo_root / str(index["daily_dir"])
        except (OSError, json.JSONDecodeError, KeyError):
            return None
        return {
            "score_model": SCORE_MODEL,
            "rolling_7d": self._read_or_empty(daily_dir / "rolling_7d.json", 7),
            "rolling_30d": self._read_or_empty(daily_dir / "rolling_30d.json", 30),
        }
