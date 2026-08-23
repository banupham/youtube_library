#!/usr/bin/env python3
"""Local bridge for the default-browser YouTube Home collector extension.

Runs a localhost HTTP server. The browser extension posts a Home snapshot here;
the bridge saves it under data/home_snapshots/ and runs the existing classifier.

Usage:
    python scripts/homepage/home_bridge.py

Then open YouTube Home in your normal browser profile and click the extension.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-classify",
        action="store_true",
        help="Save snapshots only; do not run classify_homepage.py",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    snapshot_dir = repo_root / "data" / "home_snapshots"
    classified_dir = repo_root / "data" / "home_classified"
    classifier = repo_root / "scripts" / "classification" / "classify_homepage.py"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    classified_dir.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryBridge/0.1"

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
            if self.path != "/collect":
                self._json_response(404, {"error": "not_found"})
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                self._json_response(400, {"error": "invalid_json", "detail": str(exc)})
                return

            items = payload.get("items")
            if payload.get("source") != "youtube_home" or not isinstance(items, list):
                self._json_response(400, {"error": "invalid_snapshot_schema"})
                return

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"home_{timestamp}.json"
            snapshot_path = snapshot_dir / filename
            classified_path = classified_dir / filename

            snapshot_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            classified_value: str | None = None
            if not args.no_classify:
                try:
                    subprocess.run(
                        [
                            sys.executable,
                            str(classifier),
                            str(snapshot_path),
                            "--output",
                            str(classified_path),
                        ],
                        cwd=str(repo_root),
                        check=True,
                    )
                    classified_value = str(classified_path.relative_to(repo_root))
                except subprocess.CalledProcessError as exc:
                    self._json_response(
                        500,
                        {
                            "error": "classification_failed",
                            "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                            "returncode": exc.returncode,
                        },
                    )
                    return

            result = {
                "ok": True,
                "item_count": len(items),
                "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                "classified_path": classified_value,
            }
            print(
                f"Collected {len(items)} videos -> {result['snapshot_path']}"
                + (f" -> {classified_value}" if classified_value else "")
            )
            self._json_response(200, result)

        def log_message(self, format: str, *values: object) -> None:
            print(f"[bridge] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Home Bridge: http://{args.host}:{args.port}")
    print("Giữ cửa sổ terminal này mở, sau đó dùng extension trên YouTube Home.")
    print("Nhấn Ctrl+C để dừng.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Bridge stopped.")


if __name__ == "__main__":
    main()
