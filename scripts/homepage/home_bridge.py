#!/usr/bin/env python3
"""Local bridge for the default-browser YouTube Home collector extension.

Pipeline:
browser Home snapshot
  -> save raw snapshot
  -> optional YouTube Data API enrichment when YOUTUBE_API_KEY is set
  -> v2 context/entity classifier
  -> recommendation-exposure profile JSON + HTML report

Usage:
    python scripts/homepage/home_bridge.py

Optional:
    set YOUTUBE_API_KEY=...
    python scripts/homepage/home_bridge.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-classify", action="store_true")
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--no-profile", action="store_true")
    return parser.parse_args()


def run_command(command: list[str], repo_root: Path) -> None:
    subprocess.run(command, cwd=str(repo_root), check=True)


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    snapshot_dir = repo_root / "data" / "home_snapshots"
    enriched_dir = repo_root / "data" / "home_enriched"
    classified_dir = repo_root / "data" / "home_classified"
    profile_dir = repo_root / "data" / "profile_reports"

    classifier = repo_root / "scripts" / "classification" / "classify_homepage_v2.py"
    enricher = repo_root / "scripts" / "enrichment" / "youtube_enrich.py"
    profile_builder = repo_root / "scripts" / "profile" / "build_profile_report.py"

    for folder in (snapshot_dir, enriched_dir, classified_dir, profile_dir):
        folder.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryBridge/0.2"

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
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception as exc:
                self._json_response(400, {"error": "invalid_json", "detail": str(exc)})
                return

            items = payload.get("items")
            if payload.get("source") != "youtube_home" or not isinstance(items, list):
                self._json_response(400, {"error": "invalid_snapshot_schema"})
                return

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"home_{timestamp}.json"
            stem = Path(filename).stem

            snapshot_path = snapshot_dir / filename
            enriched_path = enriched_dir / filename
            classified_path = classified_dir / filename
            profile_json = profile_dir / f"{stem}.profile.json"
            profile_html = profile_dir / f"{stem}.profile.html"

            snapshot_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            classification_input = snapshot_path
            enrichment_status = "skipped"
            api_key_available = bool(os.environ.get("YOUTUBE_API_KEY"))

            if not args.no_enrich and api_key_available:
                try:
                    run_command(
                        [sys.executable, str(enricher), str(snapshot_path), "--output", str(enriched_path)],
                        repo_root,
                    )
                    classification_input = enriched_path
                    enrichment_status = "ok"
                except subprocess.CalledProcessError as exc:
                    enrichment_status = f"failed:{exc.returncode}"
                    print("Warning: API enrichment failed; continuing with Home-visible data.")

            classified_value = None
            profile_json_value = None
            profile_html_value = None

            if not args.no_classify:
                try:
                    run_command(
                        [sys.executable, str(classifier), str(classification_input), "--output", str(classified_path)],
                        repo_root,
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

                if not args.no_profile:
                    try:
                        run_command(
                            [
                                sys.executable,
                                str(profile_builder),
                                str(classified_path),
                                "--json-output",
                                str(profile_json),
                                "--html-output",
                                str(profile_html),
                            ],
                            repo_root,
                        )
                        profile_json_value = str(profile_json.relative_to(repo_root))
                        profile_html_value = str(profile_html.relative_to(repo_root))
                    except subprocess.CalledProcessError as exc:
                        print(f"Warning: profile report failed ({exc.returncode}).")

            result = {
                "ok": True,
                "item_count": len(items),
                "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                "enrichment": enrichment_status,
                "classified_path": classified_value,
                "profile_json_path": profile_json_value,
                "profile_html_path": profile_html_value,
            }
            print(
                f"Collected {len(items)} videos -> {result['snapshot_path']}"
                + (f" -> {classified_value}" if classified_value else "")
                + (f" -> {profile_html_value}" if profile_html_value else "")
            )
            self._json_response(200, result)

        def log_message(self, format: str, *values: object) -> None:
            print(f"[bridge] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Home Bridge v0.2: http://{args.host}:{args.port}")
    print("Classifier: v2 context/entity + intent separation")
    if os.environ.get("YOUTUBE_API_KEY"):
        print("YouTube API enrichment: ENABLED")
    else:
        print("YouTube API enrichment: disabled (set YOUTUBE_API_KEY to enable)")
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
