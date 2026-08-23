#!/usr/bin/env python3
"""Central ingestion gateway for community profiles and collector snapshots.

External canonical port: 8770.

The central server exposes community APIs plus the browser collector compatibility
endpoints. During the Chrome transition it owns (or reuses) the legacy browser
profile engine on an internal loopback port and proxies /collect + /finalize to
it. Participants therefore run only this central entrypoint.

Evidence layers remain separated:
* POST /v1/profile accepts sanitized profile summaries and rebuilds the creator
  community report.
* POST /v1/android/snapshot accepts bounded raw Accessibility snapshots.
* POST /collect and /finalize are Chrome compatibility endpoints routed to the
  internal browser profile engine during migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY_BYTES = 2_000_000
ALLOWED_PLATFORMS = {"browser", "android", "other"}
YOUTUBE_ANDROID_PACKAGE = "com.google.android.youtube"
ANDROID_EXTRACTION_MODE = "android_accessibility_node_tree_read_only"
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--input-dir", default="data/community_profiles")
    parser.add_argument("--android-ingest-dir", default="data/android_ingest")
    parser.add_argument("--report-json", default="data/community_reports/current.json")
    parser.add_argument("--report-html", default="data/community_reports/current.html")
    parser.add_argument(
        "--browser-engine-port",
        type=int,
        default=8765,
        help="Internal loopback port for the transitional Chrome profile engine.",
    )
    parser.add_argument(
        "--no-browser-engine",
        action="store_true",
        help="Do not auto-start the transitional Chrome profile engine.",
    )
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


def validate_android_ingest(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors: list[str] = []
    for key in ("schema_version", "participant_id", "device_id", "profile_slot", "sent_at", "snapshot"):
        if key not in payload:
            errors.append(f"missing {key}")
    if payload.get("schema_version") != "1.0.0":
        errors.append("unsupported schema_version")

    for key, minimum, maximum in (
        ("participant_id", 4, 200),
        ("device_id", 4, 200),
        ("profile_slot", 1, 120),
    ):
        value = str(payload.get(key) or "")
        if not minimum <= len(value) <= maximum:
            errors.append(f"invalid {key}")

    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        errors.append("snapshot must be an object")
        return errors

    if snapshot.get("schema_version") != "1.0.0":
        errors.append("unsupported snapshot.schema_version")
    if snapshot.get("platform") != "android":
        errors.append("snapshot.platform must be android")
    if snapshot.get("source_package") != YOUTUBE_ANDROID_PACKAGE:
        errors.append("snapshot.source_package must be YouTube Android")
    if snapshot.get("extraction_mode") != ANDROID_EXTRACTION_MODE:
        errors.append("invalid snapshot.extraction_mode")

    captured_at = str(snapshot.get("captured_at") or "")
    if len(captured_at) < 10 or not DAY_RE.match(captured_at[:10]):
        errors.append("invalid snapshot.captured_at")

    signature = str(snapshot.get("tree_signature") or "")
    if not 8 <= len(signature) <= 128:
        errors.append("invalid snapshot.tree_signature")

    nodes = snapshot.get("nodes")
    if not isinstance(nodes, list):
        errors.append("snapshot.nodes must be a list")
    elif len(nodes) > 450:
        errors.append("snapshot.nodes exceeds 450")

    try:
        node_count = int(snapshot.get("node_count"))
        if not 0 <= node_count <= 450:
            errors.append("snapshot.node_count outside [0,450]")
        elif isinstance(nodes, list) and node_count != len(nodes):
            errors.append("snapshot.node_count does not match nodes length")
    except (TypeError, ValueError):
        errors.append("invalid snapshot.node_count")

    surface = snapshot.get("surface_guess")
    if not isinstance(surface, dict) or not str(surface.get("surface") or ""):
        errors.append("invalid snapshot.surface_guess")
    return errors


def file_contains_tree_signature(path: Path, signature: str) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str((row.get("snapshot") or {}).get("tree_signature") or "") == signature:
                    return True
    except OSError:
        return False
    return False


def port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    input_dir = resolve(args.input_dir)
    android_ingest_dir = resolve(args.android_ingest_dir)
    report_json = resolve(args.report_json)
    report_html = resolve(args.report_html)
    report_builder = repo_root / "scripts" / "community" / "build_community_report.py"
    browser_engine_script = repo_root / "scripts" / "homepage" / "home_bridge.py"
    input_dir.mkdir(parents=True, exist_ok=True)
    android_ingest_dir.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("YT_LIBRARY_COMMUNITY_TOKEN")
    write_lock = threading.Lock()

    browser_engine_process: subprocess.Popen | None = None
    browser_engine_host = "127.0.0.1"
    browser_engine_port = int(args.browser_engine_port)

    if not args.no_browser_engine:
        if port_open(browser_engine_host, browser_engine_port):
            print(
                f"Chrome profile engine -> reuse existing "
                f"http://{browser_engine_host}:{browser_engine_port}"
            )
        else:
            browser_engine_process = subprocess.Popen(
                [
                    sys.executable,
                    str(browser_engine_script),
                    "--host",
                    browser_engine_host,
                    "--port",
                    str(browser_engine_port),
                ],
                cwd=str(repo_root),
            )
            deadline = time.time() + 8.0
            while time.time() < deadline and not port_open(browser_engine_host, browser_engine_port):
                if browser_engine_process.poll() is not None:
                    break
                time.sleep(0.15)
            if port_open(browser_engine_host, browser_engine_port):
                print(
                    f"Chrome profile engine -> managed internally at "
                    f"http://{browser_engine_host}:{browser_engine_port}"
                )
            else:
                print(
                    "WARNING: Chrome profile engine did not become ready. "
                    "Android/community APIs can still run, but Chrome /collect and /finalize will fail."
                )

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

    def proxy_browser_engine(endpoint: str, payload: object) -> tuple[int, dict]:
        if not port_open(browser_engine_host, browser_engine_port):
            return 503, {
                "error": "browser_engine_unavailable",
                "detail": f"internal browser engine not listening on {browser_engine_host}:{browser_engine_port}",
            }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"http://{browser_engine_host}:{browser_engine_port}{endpoint}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read()
                try:
                    data = json.loads(raw.decode("utf-8"))
                except Exception:
                    data = {"ok": True, "upstream_text": raw.decode("utf-8", errors="replace")[:1000]}
                return int(response.status), data
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                data = {
                    "error": "browser_engine_http_error",
                    "status": exc.code,
                    "detail": raw.decode("utf-8", errors="replace")[:1000],
                }
            return int(exc.code), data
        except Exception as exc:
            return 502, {"error": "browser_engine_proxy_failed", "detail": str(exc)}

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryCommunity/1.2"

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not token:
                return True
            return self.headers.get("Authorization") == f"Bearer {token}"

        def _read_json_body(self) -> object | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "invalid_content_length"})
                return None
            if length <= 0 or length > MAX_BODY_BYTES:
                self._json(413, {"error": "invalid_body_size"})
                return None
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception as exc:
                self._json(400, {"error": "invalid_json", "detail": str(exc)})
                return None

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(
                    200,
                    {
                        "ok": True,
                        "service": "community",
                        "version": "1.2.0",
                        "canonical_port": args.port,
                        "browser_collect": "/collect",
                        "browser_finalize": "/finalize",
                        "browser_engine_internal": {
                            "host": browser_engine_host,
                            "port": browser_engine_port,
                            "ready": port_open(browser_engine_host, browser_engine_port),
                        },
                        "profile_ingest": "/v1/profile",
                        "android_snapshot_ingest": "/v1/android/snapshot",
                    },
                )
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {
                "/collect",
                "/finalize",
                "/v1/profile",
                "/v1/android/snapshot",
            }:
                self._json(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            payload = self._read_json_body()
            if payload is None:
                return

            if self.path in {"/collect", "/finalize"}:
                status, response = proxy_browser_engine(self.path, payload)
                self._json(status, response)
            elif self.path == "/v1/android/snapshot":
                self._handle_android_snapshot(payload)
            else:
                self._handle_profile(payload)

        def _handle_profile(self, payload: object) -> None:
            errors = validate_submission(payload)
            if errors:
                self._json(400, {"error": "invalid_submission", "details": errors[:20]})
                return
            assert isinstance(payload, dict)

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

        def _handle_android_snapshot(self, payload: object) -> None:
            errors = validate_android_ingest(payload)
            if errors:
                self._json(400, {"error": "invalid_android_snapshot", "details": errors[:20]})
                return
            assert isinstance(payload, dict)
            snapshot = payload["snapshot"]
            assert isinstance(snapshot, dict)

            participant_id = str(payload["participant_id"])
            device_id = str(payload["device_id"])
            profile_slot = str(payload["profile_slot"])
            day = str(snapshot["captured_at"])[:10]
            signature = str(snapshot["tree_signature"])
            surface = str((snapshot.get("surface_guess") or {}).get("surface") or "unknown")

            participant_dir = android_ingest_dir / f"participant_{safe_short(participant_id)}"
            device_dir = participant_dir / (
                f"device_{safe_short(device_id)}__slot_{safe_short(profile_slot)}"
            )
            path = device_dir / f"{day}.jsonl"

            with write_lock:
                device_dir.mkdir(parents=True, exist_ok=True)
                duplicate = file_contains_tree_signature(path, signature)
                if not duplicate:
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
                        )

            self._json(
                200,
                {
                    "ok": True,
                    "duplicate": duplicate,
                    "tree_signature": signature,
                    "surface": surface,
                    "stored_day": day,
                    "profile_report_updated": False,
                },
            )

        def log_message(self, format: str, *values: object) -> None:
            print(f"[community] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Central Server v1.2: http://{args.host}:{args.port}")
    print("Chrome external API: POST /collect + POST /finalize")
    print("Android external API: POST /v1/android/snapshot")
    print("Analyzed profile API: POST /v1/profile")
    print(
        f"Chrome transitional engine: internal "
        f"{browser_engine_host}:{browser_engine_port} "
        f"({'ready' if port_open(browser_engine_host, browser_engine_port) else 'NOT READY'})"
    )
    print(f"Community profiles -> {input_dir}")
    print(f"Android raw ingest -> {android_ingest_dir}")
    print(f"Creator report -> {report_html}")
    if token:
        print("Bearer token: REQUIRED (YT_LIBRARY_COMMUNITY_TOKEN)")
    else:
        print(
            "Bearer token: disabled; set YT_LIBRARY_COMMUNITY_TOKEN before exposing beyond localhost"
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if browser_engine_process is not None and browser_engine_process.poll() is None:
            browser_engine_process.terminate()
            try:
                browser_engine_process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                browser_engine_process.kill()


if __name__ == "__main__":
    main()
