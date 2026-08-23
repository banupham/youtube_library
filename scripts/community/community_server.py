#!/usr/bin/env python3
"""Receive sanitized profile summaries and rebuild the creator community report.

This is intentionally a small ingestion gateway. It never receives YouTube
cookies, account credentials, raw Home/Up Next rows, subscribed-channel names,
or other browsing/session secrets under the v1 submission contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY_BYTES = 2_000_000
ALLOWED_PLATFORMS = {"browser", "android", "other"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--input-dir", default="data/community_profiles")
    parser.add_argument("--report-json", default="data/community_reports/current.json")
    parser.add_argument("--report-html", default="data/community_reports/current.html")
    return parser.parse_args()


def safe_short(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def validate_submission(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors = []
    required = (
        "schema_version",
        "participant_id",
        "device_id",
        "profile_id",
        "profile_key",
        "updated_at",
        "certainty_score",
        "interest_weights",
    )
    for key in required:
        if key not in payload:
            errors.append(f"missing {key}")
    if payload.get("schema_version") != "1.0.0":
        errors.append("unsupported schema_version")
    for key in ("participant_id", "device_id", "profile_id", "profile_key"):
        value = str(payload.get(key) or "")
        if len(value) < 4 or len(value) > 200:
            errors.append(f"invalid {key}")
    try:
        certainty = float(payload.get("certainty_score") or 0.0)
        if not 0.0 <= certainty <= 1.0:
            errors.append("certainty_score outside [0,1]")
    except (TypeError, ValueError):
        errors.append("invalid certainty_score")
    interests = payload.get("interest_weights")
    if not isinstance(interests, list) or not interests:
        errors.append("interest_weights must be a non-empty list")
    else:
        for index, row in enumerate(interests[:100]):
            if not isinstance(row, dict) or not str(row.get("id") or ""):
                errors.append(f"invalid interest_weights[{index}]")
                continue
            try:
                weight = float(row.get("predicted_weight") or 0.0)
                if not 0.0 <= weight <= 1.0:
                    errors.append(f"interest_weights[{index}].predicted_weight outside [0,1]")
            except (TypeError, ValueError):
                errors.append(f"invalid interest_weights[{index}].predicted_weight")
    collector = payload.get("collector") or {}
    if collector and str(collector.get("platform") or "other") not in ALLOWED_PLATFORMS:
        errors.append("invalid collector.platform")
    forbidden_keys = {
        "cookie",
        "cookies",
        "authorization_header",
        "google_email",
        "email",
        "password",
        "subscription_channels",
        "raw_items",
        "items",
    }
    present_forbidden = forbidden_keys.intersection(payload)
    if present_forbidden:
        errors.append("forbidden top-level fields: " + ", ".join(sorted(present_forbidden)))
    return errors


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    input_dir = resolve(args.input_dir)
    report_json = resolve(args.report_json)
    report_html = resolve(args.report_html)
    report_builder = repo_root / "scripts" / "community" / "build_community_report.py"
    input_dir.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("YT_LIBRARY_COMMUNITY_TOKEN")
    write_lock = threading.Lock()

    def rebuild_report() -> None:
        subprocess.run(
            [
                sys.executable,
                str(report_builder),
                "--input-dir",
                str(input_dir),
                "--json-output",
                str(report_json),
                "--html-output",
                str(report_html),
            ],
            cwd=str(repo_root),
            check=True,
        )

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryCommunity/1.0"

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not token:
                return True
            return self.headers.get("Authorization") == f"Bearer {token}"

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(200, {"ok": True, "service": "community", "version": "1.0.0"})
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/profile":
                self._json(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "invalid_content_length"})
                return
            if length <= 0 or length > MAX_BODY_BYTES:
                self._json(413, {"error": "invalid_body_size"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception as exc:
                self._json(400, {"error": "invalid_json", "detail": str(exc)})
                return
            errors = validate_submission(payload)
            if errors:
                self._json(400, {"error": "invalid_submission", "details": errors[:20]})
                return

            participant_id = str(payload["participant_id"])
            profile_key = str(payload["profile_key"])
            filename = f"participant_{safe_short(participant_id)}__profile_{safe_short(profile_key)}.json"
            path = input_dir / filename
            with write_lock:
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                try:
                    rebuild_report()
                    report_status = "updated"
                except subprocess.CalledProcessError as exc:
                    report_status = f"failed:{exc.returncode}"

            self._json(
                200,
                {
                    "ok": True,
                    "profile_key": profile_key,
                    "stored": filename,
                    "community_report_status": report_status,
                },
            )

        def log_message(self, format: str, *values: object) -> None:
            print(f"[community] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Community Server v1.0: http://{args.host}:{args.port}")
    print("POST /v1/profile accepts sanitized profile summaries only")
    print(f"Community profiles -> {input_dir}")
    print(f"Creator report -> {report_html}")
    if token:
        print("Bearer token: REQUIRED (YT_LIBRARY_COMMUNITY_TOKEN)")
    else:
        print("Bearer token: disabled; set YT_LIBRARY_COMMUNITY_TOKEN before exposing beyond localhost")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
