#!/usr/bin/env python3
"""Sanitize a longitudinal profile and optionally submit it to a community server.

No cookies, credentials, raw recommendation rows, subscribed-channel names, or
profile labels are included. A stable random participant/device identity is
created locally in data/collector_identity.json and is ignored by git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
import urllib.error
import urllib.request
from pathlib import Path

SCHEMA_VERSION = "1.0.0"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_or_create_identity(path: Path) -> dict:
    if path.exists():
        try:
            identity = read_json(path)
            if identity.get("participant_id") and identity.get("device_id"):
                return identity
        except (OSError, json.JSONDecodeError):
            pass
    identity = {
        "version": "1.0.0",
        "participant_id": f"participant-{uuid.uuid4()}",
        "device_id": f"device-{uuid.uuid4()}",
        "note": "Local random IDs only; do not replace with email/account identifiers.",
    }
    write_json(path, identity)
    return identity


def keep_number(row: dict, key: str) -> float:
    try:
        return max(0.0, min(1.0, float(row.get(key) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def sanitize_interest(row: dict) -> dict:
    return {
        "id": str(row.get("id") or "")[:120],
        "name_vi": str(row.get("name_vi") or "")[:160] or None,
        "predicted_weight": keep_number(row, "predicted_weight"),
        "today_weight": keep_number(row, "today_weight"),
        "weight_7d": keep_number(row, "weight_7d"),
        "weight_30d": keep_number(row, "weight_30d"),
        "long_term_weight": keep_number(row, "long_term_weight"),
        "trend_state": str(row.get("trend_state") or "")[:40] or None,
        "home_weight": keep_number(row, "home_weight"),
        "up_next_weight": keep_number(row, "up_next_weight"),
        "subscription_weight": keep_number(row, "subscription_weight"),
    }


def sanitize_intent(row: dict) -> dict:
    return {
        "id": str(row.get("id") or "")[:80],
        "label": str(row.get("label") or "")[:120] or None,
        "weight": keep_number(row, "weight"),
    }


def sanitize_term(row: dict) -> dict:
    return {
        "value": str(row.get("value") or "").strip()[:200],
        "weight": keep_number(row, "weight"),
        "today_weight": keep_number(row, "today_weight"),
        "weight_7d": keep_number(row, "weight_7d"),
        "weight_30d": keep_number(row, "weight_30d"),
        "long_term_weight": keep_number(row, "long_term_weight"),
        "trend_state": str(row.get("trend_state") or "")[:40] or None,
    }


def build_submission(profile: dict, identity: dict, platform: str, agent_version: str | None) -> dict:
    profile_identity = profile.get("profile") or profile.get("collector_profile") or {}
    profile_id = str(profile_identity.get("profile_id") or "").strip()
    if not profile_id:
        raise ValueError("profile JSON does not contain profile.profile_id")
    participant_id = str(identity["participant_id"])
    device_id = str(identity["device_id"])
    profile_key = "community-profile-" + hashlib.sha256(
        f"{participant_id}|{profile_id}".encode("utf-8")
    ).hexdigest()[:24]
    temporal = profile.get("temporal_profile") or {}

    interests = [
        sanitize_interest(row)
        for row in profile.get("interest_weights") or []
        if row.get("id")
    ][:36]
    intents = [
        sanitize_intent(row)
        for row in profile.get("intent_weights") or []
        if row.get("id")
    ][:16]
    keywords = [
        sanitize_term(row)
        for row in profile.get("keyword_trends") or []
        if str(row.get("value") or "").strip()
    ][:50]
    tags = [
        sanitize_term(row)
        for row in profile.get("tag_trends") or []
        if str(row.get("value") or "").strip()
    ][:50]

    return {
        "schema_version": SCHEMA_VERSION,
        "participant_id": participant_id,
        "device_id": device_id,
        "profile_id": profile_id,
        "profile_key": profile_key,
        "behavior_profile_name": str(profile.get("behavior_profile_name") or "")[:160] or None,
        "analysis_version": str(profile.get("analysis_version") or "")[:40] or None,
        "updated_at": str(profile.get("updated_at") or ""),
        "certainty_score": max(0.0, min(1.0, float(profile.get("certainty_score") or 0.0))),
        "daily_observation_count": max(0, int(temporal.get("daily_observation_count") or 0)),
        "collector": {
            "platform": platform,
            "agent_version": agent_version,
            "submission_mode": "sanitized_profile_summary",
        },
        "interest_weights": interests,
        "intent_weights": intents,
        "keyword_trends": keywords,
        "tag_trends": tags,
    }


def post_submission(endpoint: str, payload: dict, token: str | None, timeout: float = 15.0) -> dict:
    url = endpoint.rstrip("/") + "/v1/profile"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "YouTubeLibraryCollector/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {"ok": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_json")
    parser.add_argument("--endpoint", default=os.environ.get("YT_LIBRARY_COMMUNITY_ENDPOINT"))
    parser.add_argument("--token", default=os.environ.get("YT_LIBRARY_COMMUNITY_TOKEN"))
    parser.add_argument("--platform", choices=["browser", "android", "other"], default="browser")
    parser.add_argument("--agent-version", default=None)
    parser.add_argument("--identity-file", default="data/collector_identity.json")
    parser.add_argument("--output", default=None, help="Optional local sanitized submission JSON")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    profile_path = resolve(args.profile_json)
    identity_path = resolve(args.identity_file)
    identity = load_or_create_identity(identity_path)
    submission = build_submission(
        read_json(profile_path),
        identity,
        platform=args.platform,
        agent_version=args.agent_version,
    )

    if args.output:
        write_json(resolve(args.output), submission)

    if args.endpoint:
        try:
            result = post_submission(args.endpoint, submission, args.token)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SystemExit(f"Community submission HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"Community submission failed: {exc.reason}") from exc
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({
            "ok": True,
            "profile_key": submission["profile_key"],
            "participant_id": submission["participant_id"],
            "note": "No endpoint configured; sanitized submission built locally only.",
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
