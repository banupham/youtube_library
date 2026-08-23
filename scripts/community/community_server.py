#!/usr/bin/env python3
"""Single-process central server for YouTube Library.

Canonical runtime:

    python scripts/community/community_server.py

One process, one port (8770 by default). Chrome collection, Android ingest,
natural interaction evidence, profile analysis, community aggregation, and
human-facing HTML are exposed from this entrypoint.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from browser_pipeline import BrowserPipeline
from interaction_store import InteractionStore
from submit_profile import build_submission

MAX_BODY_BYTES = 2_000_000
ALLOWED_PLATFORMS = {"browser", "android", "other"}
YOUTUBE_ANDROID_PACKAGE = "com.google.android.youtube"
ANDROID_EXTRACTION_MODE = "android_accessibility_node_tree_read_only"
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROFILE_SHORT_RE = re.compile(r"^[A-Za-z0-9]{1,32}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--input-dir", default="data/community_profiles")
    parser.add_argument("--android-ingest-dir", default="data/android_ingest")
    parser.add_argument("--report-json", default="data/community_reports/current.json")
    parser.add_argument("--report-html", default="data/community_reports/current.html")
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--no-classify", action="store_true")
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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def interaction_card(summary: dict | None) -> str:
    if not summary:
        return ""
    seven = summary.get("rolling_7d") or {}
    thirty = summary.get("rolling_30d") or {}
    counts = seven.get("event_counts") or {}
    sub = seven.get("video_open_subscription_counts") or {}
    return f"""
<section style="margin:20px auto;max-width:1100px;padding:0 20px">
<div style="background:#171b22;border:1px solid #303742;border-radius:16px;padding:20px;color:#eef2f7;font-family:system-ui,sans-serif">
<h2 style="margin-top:0">Natural interactions</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px">
<div><b>7 ngày</b><br>score {html.escape(str(seven.get('score_total', 0)))} · {html.escape(str(seven.get('event_count', 0)))} events</div>
<div><b>30 ngày</b><br>score {html.escape(str(thirty.get('score_total', 0)))} · {html.escape(str(thirty.get('event_count', 0)))} events</div>
<div><b>7d Like / Comment</b><br>{html.escape(str(counts.get('like', 0)))} / {html.escape(str(counts.get('comment_submit', 0)))}</div>
<div><b>Video mở 7d</b><br>subscribed {html.escape(str(sub.get('subscribed', 0)))} · non-sub {html.escape(str(sub.get('not_subscribed', 0)))} · unknown {html.escape(str(sub.get('unknown', 0)))}</div>
</div>
<p style="color:#aab2bf;margin-bottom:0">Score model: natural_interaction_v1. Comment chỉ lưu sự kiện đã gửi, không lưu nội dung comment.</p>
</div></section>
"""


def empty_dashboard() -> str:
    return """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube Library</title><style>
body{margin:0;background:#0f1115;color:#f4f6f8;font-family:Inter,system-ui,sans-serif}
main{max-width:980px;margin:auto;padding:38px 20px}.card{background:#181c22;border:1px solid #303640;border-radius:18px;padding:24px}
a{color:#a9c1ff}code{background:#252a33;padding:3px 7px;border-radius:7px}.muted{color:#aab2bf}
</style></head><body><main><div class="card"><h1>YouTube Library</h1>
<p>Central server đang chạy. Chưa có đủ community profile để tạo Creator Dashboard.</p>
<p class="muted">Chrome và Android có thể tiếp tục gửi dữ liệu vào cùng server này.</p>
<p><a href="/health">Xem trạng thái server</a></p></div></main></body></html>"""


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
    input_dir.mkdir(parents=True, exist_ok=True)
    android_ingest_dir.mkdir(parents=True, exist_ok=True)
    report_html.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("YT_LIBRARY_COMMUNITY_TOKEN")
    write_lock = threading.RLock()
    browser_pipeline = BrowserPipeline(repo_root, no_enrich=args.no_enrich, no_classify=args.no_classify)
    interaction_store = InteractionStore(repo_root)

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

    def store_community_submission(submission: dict) -> tuple[bool, str]:
        errors = validate_submission(submission)
        if errors:
            return False, "invalid:" + ";".join(errors[:5])
        participant_id = str(submission["participant_id"])
        profile_key = str(submission["profile_key"])
        filename = f"participant_{safe_short(participant_id)}__profile_{safe_short(profile_key)}.json"
        path = input_dir / filename
        with write_lock:
            write_json(path, submission)
            try:
                rebuild_report()
            except subprocess.CalledProcessError as exc:
                return False, f"report_failed:{exc.returncode}"
        return True, filename

    def attach_interactions_to_profile(response: dict) -> dict | None:
        profile_id = str(response.get("profile_id") or "")
        summary = interaction_store.summary_for_profile(profile_id)
        if not summary:
            return None
        for key in ("profile_json_path", "library_path"):
            value = response.get(key)
            if not value:
                continue
            path = repo_root / str(value)
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["natural_interactions"] = summary
                write_json(path, payload)
            except (OSError, json.JSONDecodeError):
                continue
        return summary

    def promote_browser_profile(finalize_request: object, response: dict) -> str:
        if not isinstance(finalize_request, dict):
            return "skipped:invalid_finalize_request"
        collector = finalize_request.get("collector_profile")
        if not isinstance(collector, dict):
            return "skipped:missing_collector_profile"
        participant_id = str(collector.get("participant_id") or "").strip()
        device_id = str(collector.get("device_id") or "").strip()
        if len(participant_id) < 4 or len(device_id) < 4:
            return "skipped:missing_participant_identity"
        profile_path_value = response.get("profile_json_path")
        if not profile_path_value:
            return "skipped:missing_profile_path"
        profile_path = repo_root / str(profile_path_value)
        try:
            profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            submission = build_submission(
                profile_payload,
                {"participant_id": participant_id, "device_id": device_id},
                platform="browser",
                agent_version="0.7.0",
            )
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            return f"failed:build_submission:{exc}"
        ok, detail = store_community_submission(submission)
        return "updated:" + detail if ok else "failed:" + detail

    try:
        rebuild_report()
    except subprocess.CalledProcessError as exc:
        print(f"Warning: initial creator dashboard build failed: {exc}")

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryCentral/2.2"

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

        def _html(self, status: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _html_file(self, path: Path) -> None:
            try:
                self._html(200, path.read_text(encoding="utf-8"))
            except OSError:
                self._html(404, empty_dashboard())

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
            path = self.path.split("?", 1)[0]
            if path in {"/", "/dashboard"}:
                if report_html.exists():
                    self._html_file(report_html)
                else:
                    self._html(200, empty_dashboard())
                return
            if path.startswith("/profile/"):
                short_id = path[len("/profile/"):].strip()
                if not PROFILE_SHORT_RE.fullmatch(short_id):
                    self._html(400, "<h1>Invalid profile id</h1>")
                    return
                profile_html = repo_root / "data" / "profile_reports" / f"profile_{short_id}__current.profile.html"
                profile_json = repo_root / "data" / "profile_reports" / f"profile_{short_id}__current.profile.json"
                if not profile_html.exists():
                    self._html(404, f"<h1>Profile chưa có report</h1><p>{html.escape(short_id)}</p><p><a href='/'>Dashboard</a></p>")
                    return
                try:
                    page = profile_html.read_text(encoding="utf-8")
                    summary = None
                    if profile_json.exists():
                        profile = json.loads(profile_json.read_text(encoding="utf-8"))
                        identity = profile.get("profile") or profile.get("collector_profile") or {}
                        profile_id = str(identity.get("profile_id") or "")
                        if profile_id:
                            summary = interaction_store.summary_for_profile(profile_id)
                    card = interaction_card(summary)
                    page = page.replace("</body>", card + "</body>") if card else page
                    self._html(200, page)
                except (OSError, json.JSONDecodeError):
                    self._html_file(profile_html)
                return
            if path == "/health":
                self._json(
                    200,
                    {
                        "ok": True,
                        "service": "youtube-library-central",
                        "version": "2.2.0",
                        "port": args.port,
                        "single_process": True,
                        "dashboard": "/",
                        "browser_collect": "/collect",
                        "browser_finalize": "/finalize",
                        "profile_ingest": "/v1/profile",
                        "android_snapshot_ingest": "/v1/android/snapshot",
                        "interaction_ingest": "/v1/interaction",
                    },
                )
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            allowed = {"/collect", "/finalize", "/v1/profile", "/v1/android/snapshot", "/v1/interaction"}
            if self.path not in allowed:
                self._json(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            payload = self._read_json_body()
            if payload is None:
                return

            if self.path == "/collect":
                status, response = browser_pipeline.collect(payload)
                self._json(status, response)
            elif self.path == "/finalize":
                status, response = browser_pipeline.finalize(payload)
                if status == 200:
                    response["natural_interactions"] = attach_interactions_to_profile(response)
                    response["community_profile_status"] = promote_browser_profile(payload, response)
                self._json(status, response)
            elif self.path == "/v1/android/snapshot":
                self._handle_android_snapshot(payload)
            elif self.path == "/v1/interaction":
                status, response = interaction_store.ingest(payload)
                self._json(status, response)
            else:
                self._handle_profile(payload)

        def _handle_profile(self, payload: object) -> None:
            errors = validate_submission(payload)
            if errors:
                self._json(400, {"error": "invalid_submission", "details": errors[:20]})
                return
            assert isinstance(payload, dict)
            ok, detail = store_community_submission(payload)
            self._json(
                200 if ok else 500,
                {
                    "ok": ok,
                    "profile_key": payload.get("profile_key"),
                    "stored": detail if ok else None,
                    "community_report_status": "updated" if ok else detail,
                    "dashboard_url": "/",
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
            device_dir = participant_dir / f"device_{safe_short(device_id)}__slot_{safe_short(profile_slot)}"
            path = device_dir / f"{day}.jsonl"
            with write_lock:
                device_dir.mkdir(parents=True, exist_ok=True)
                duplicate = file_contains_tree_signature(path, signature)
                if not duplicate:
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._json(200, {"ok": True, "duplicate": duplicate, "tree_signature": signature, "surface": surface, "stored_day": day, "profile_report_updated": False})

        def log_message(self, format: str, *values: object) -> None:
            print(f"[central] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Central Server v2.2: http://{args.host}:{args.port}")
    print(f"Dashboard: http://127.0.0.1:{args.port}/")
    print("Chrome: POST /collect + POST /finalize")
    print("Android: POST /v1/android/snapshot")
    print("Natural interactions: POST /v1/interaction")
    print("Community profile: POST /v1/profile")
    print("Runtime: ONE PROCESS / ONE PORT")
    if os.environ.get("YOUTUBE_API_KEY"):
        print("YouTube API enrichment: ENABLED")
    else:
        print("YouTube API enrichment: disabled")
    if token:
        print("Bearer token: REQUIRED")
    else:
        print("Bearer token: disabled; bind localhost unless configuring a protected deployment")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
