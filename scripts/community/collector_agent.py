#!/usr/bin/env python3
"""Watch local longitudinal profiles and automatically sync sanitized summaries.

The agent does not browse YouTube itself. Natural/read-only capture remains the
responsibility of a platform collector (browser today, Android adapter later).
Whenever that collector updates data/profile_library/profile_*.json, this agent
submits the sanitized summary to the central community service.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUBMIT_PATH = ROOT / "scripts" / "community" / "submit_profile.py"
spec = importlib.util.spec_from_file_location("submit_profile", SUBMIT_PATH)
submitter = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(submitter)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_current_profiles(folder: Path) -> list[Path]:
    paths = []
    if not folder.exists():
        return paths
    for path in sorted(folder.glob("profile_*.json")):
        name = path.name
        if name == "index.json" or ".history." in name:
            continue
        paths.append(path)
    return paths


def fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", default="data/profile_library")
    parser.add_argument("--identity-file", default="data/collector_identity.json")
    parser.add_argument("--state-file", default="data/community_sync_state.json")
    parser.add_argument("--endpoint", default=os.environ.get("YT_LIBRARY_COMMUNITY_ENDPOINT"))
    parser.add_argument("--token", default=os.environ.get("YT_LIBRARY_COMMUNITY_TOKEN"))
    parser.add_argument("--platform", choices=["browser", "android", "other"], default="browser")
    parser.add_argument("--agent-version", default="1.0.0")
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--launch-bridge", action="store_true")
    args = parser.parse_args()

    if not args.endpoint:
        raise SystemExit("Set --endpoint or YT_LIBRARY_COMMUNITY_ENDPOINT")

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path

    profile_dir = resolve(args.profile_dir)
    identity_path = resolve(args.identity_file)
    state_path = resolve(args.state_file)
    identity = submitter.load_or_create_identity(identity_path)
    state = {}
    if state_path.exists():
        try:
            state = read_json(state_path)
        except (OSError, json.JSONDecodeError):
            state = {}
    synced = dict(state.get("synced") or {})

    bridge_process = None
    if args.launch_bridge:
        bridge_process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "homepage" / "home_bridge.py")],
            cwd=str(ROOT),
        )
        print(f"Started local bridge PID {bridge_process.pid}")

    print(f"Collector participant -> {identity['participant_id']}")
    print(f"Collector device -> {identity['device_id']}")
    print(f"Watching -> {profile_dir}")
    print(f"Community endpoint -> {args.endpoint}")

    try:
        while True:
            changed = 0
            for path in list_current_profiles(profile_dir):
                key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                current = fingerprint(path)
                if synced.get(key) == current:
                    continue
                try:
                    profile = read_json(path)
                    submission = submitter.build_submission(
                        profile,
                        identity,
                        platform=args.platform,
                        agent_version=args.agent_version,
                    )
                    result = submitter.post_submission(args.endpoint, submission, args.token)
                    synced[key] = current
                    changed += 1
                    print(f"Synced {path.name} -> {result.get('profile_key', submission['profile_key'])}")
                except Exception as exc:
                    print(f"Warning: sync failed for {path}: {exc}", file=sys.stderr)

            write_json(
                state_path,
                {
                    "version": "1.0.0",
                    "participant_id": identity["participant_id"],
                    "device_id": identity["device_id"],
                    "synced": synced,
                    "last_scan_at": time.time(),
                },
            )
            if args.once:
                break
            if changed == 0:
                time.sleep(max(2.0, args.interval))
            else:
                time.sleep(1.0)
    finally:
        if bridge_process is not None and bridge_process.poll() is None:
            bridge_process.terminate()


if __name__ == "__main__":
    main()
