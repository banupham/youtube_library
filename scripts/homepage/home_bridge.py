#!/usr/bin/env python3
"""Local bridge for the default-browser YouTube Home collector extension.

Pipeline:
browser Home snapshot
  -> stable browser-profile identity
  -> save raw snapshot in that profile's data folder
  -> optional YouTube Data API enrichment when YOUTUBE_API_KEY is set
  -> v2 context/entity classifier
  -> profile-intelligence JSON + HTML pair in data/profile_reports

Usage:
    python scripts/homepage/home_bridge.py

Optional:
    set YOUTUBE_API_KEY=...
    python scripts/homepage/home_bridge.py
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
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


def profile_folder(profile: dict) -> str:
    # Raw/enriched/classified history remains partitioned by stable browser-profile ID.
    return f"profile_{profile['profile_short_id']}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inject_profile_metadata(path: Path, profile: dict) -> None:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    payload["collector_profile"] = profile
    write_json(path, payload)


def annotate_profile_html(path: Path, profile: dict) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    marker = '<div class="muted">Recommendation Prior · Home exposure</div>'
    banner = (
        '<div style="margin-bottom:10px;padding:10px 12px;border-radius:10px;'
        'background:#20232a;font-size:.92rem">'
        '<strong>Browser profile:</strong> '
        f'{html_lib.escape(profile["profile_label"])} '
        f'· <code>{html_lib.escape(profile["profile_short_id"])}</code>'
        '</div>'
    )
    if marker in text:
        text = text.replace(marker, banner + marker, 1)
    path.write_text(text, encoding="utf-8")


def fallback_profile_html(json_path: Path, html_path: Path, profile: dict) -> None:
    """Render a compact HTML report if the richer renderer fails after JSON exists."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    interests = payload.get("predicted_interest_weights") or []
    directions = payload.get("content_directions") or []
    keywords = payload.get("keyword_map") or []
    tags = payload.get("creator_tag_map") or []
    quality = payload.get("evidence_quality") or {}

    def pct(value: object) -> float:
        try:
            return float(value) * 100.0
        except (TypeError, ValueError):
            return 0.0

    bars = []
    for row in interests[:12]:
        label = html_lib.escape(str(row.get("name_vi") or row.get("id") or "Unknown"))
        share = pct(row.get("predicted_weight"))
        zone = html_lib.escape(str(row.get("zone") or ""))
        bars.append(
            '<div class="row">'
            f'<div><strong>{label}</strong><span>{zone}</span><b>{share:.1f}%</b></div>'
            f'<div class="track"><i style="width:{max(1.0, share):.2f}%"></i></div>'
            '</div>'
        )

    cards = []
    for row in directions[:8]:
        kws = ", ".join(html_lib.escape(str(x.get("value") or "")) for x in (row.get("keywords") or [])[:6])
        observed_tags = ", ".join(html_lib.escape(str(x.get("value") or "")) for x in (row.get("suggested_tags") or [])[:6])
        cards.append(
            '<article>'
            f'<small>{html_lib.escape(str(row.get("zone") or ""))} · predicted {pct(row.get("predicted_weight")):.1f}%</small>'
            f'<h3>{html_lib.escape(str(row.get("direction") or row.get("id") or "Direction"))}</h3>'
            f'<p>Opportunity <strong>{float(row.get("opportunity_score") or 0.0):.2f}</strong></p>'
            f'<p><b>Keywords:</b> {kws or "—"}</p>'
            f'<p><b>Observed tags:</b> {observed_tags or "—"}</p>'
            '</article>'
        )

    keyword_chips = "".join(
        f'<span class="chip">{html_lib.escape(str(row.get("value") or ""))}</span>' for row in keywords[:28]
    )
    tag_chips = "".join(
        f'<span class="chip">{html_lib.escape(str(row.get("value") or ""))}</span>' for row in tags[:28]
    )

    archetype = html_lib.escape(str(payload.get("archetype") or "Recommendation profile"))
    profile_label = html_lib.escape(profile["profile_label"])
    short_id = html_lib.escape(profile["profile_short_id"])
    certainty = pct(quality.get("certainty_score"))
    uncertainty = pct(quality.get("uncertainty_score"))

    rendered = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube Profile Intelligence</title>
<style>
body{{margin:0;background:#101114;color:#f4f5f7;font-family:Inter,system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:26px 18px 50px}}
.hero,.panel,article{{background:#17191e;border:1px solid #30333a;border-radius:16px}}.hero,.panel{{padding:20px;margin-bottom:16px}}h1,h2,h3{{margin:.25em 0 .6em}}
.muted,small{{color:#aeb3bd}}.stats,.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.stat,article{{padding:14px;background:#20232a}}
.row{{margin:13px 0}}.row>div:first-child{{display:flex;gap:10px;align-items:center}}.row span{{color:#aeb3bd;font-size:.8rem}}.row b{{margin-left:auto}}
.track{{height:10px;background:#2a2e36;border-radius:999px;overflow:hidden;margin-top:5px}}.track i{{display:block;height:100%;background:#9daeff;border-radius:999px}}
.chip{{display:inline-block;padding:7px 10px;margin:4px;background:#242832;border-radius:999px;font-size:.86rem}}p{{line-height:1.5}}
</style></head><body><main>
<section class="hero"><div class="muted">Browser profile: <strong>{profile_label}</strong> · {short_id}</div><h1>{archetype}</h1>
<div class="stats"><div class="stat">Certainty<br><strong>{certainty:.1f}%</strong></div><div class="stat">Uncertainty<br><strong>{uncertainty:.1f}%</strong></div><div class="stat">Video<br><strong>{int(payload.get("video_count") or 0)}</strong></div></div></section>
<section class="panel"><h2>Trọng số dự đoán</h2>{''.join(bars) or '<p class="muted">Chưa đủ dữ liệu.</p>'}</section>
<section class="panel"><h2>Hướng nội dung nên thử</h2><div class="cards">{''.join(cards) or '<p class="muted">Chưa đủ dữ liệu.</p>'}</div></section>
<section class="panel"><h2>Keyword map</h2>{keyword_chips or '<span class="muted">Chưa đủ dữ liệu.</span>'}</section>
<section class="panel"><h2>Creator tags</h2>{tag_chips or '<span class="muted">Chưa đủ dữ liệu.</span>'}</section>
</main></body></html>"""
    html_path.write_text(rendered, encoding="utf-8")


def cleanup_paths(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass


def build_profile_pair(
    *,
    profile_builder: Path,
    classified_path: Path,
    final_json: Path,
    final_html: Path,
    profile: dict,
    repo_root: Path,
) -> str:
    """Create JSON+HTML as one logical report pair; never leave JSON-only output."""
    temp_json = final_json.with_name(f".{final_json.name}.tmp")
    temp_html = final_html.with_name(f".{final_html.name}.tmp")
    cleanup_paths(temp_json, temp_html)

    renderer_status = "ok"
    command_failed = False
    try:
        run_command(
            [
                sys.executable,
                str(profile_builder),
                str(classified_path),
                "--json-output",
                str(temp_json),
                "--html-output",
                str(temp_html),
            ],
            repo_root,
        )
    except subprocess.CalledProcessError:
        command_failed = True

    # A renderer may fail after successfully writing the JSON. In that case,
    # preserve the analysis and generate a compact visual fallback from it.
    if temp_json.exists() and (not temp_html.exists() or temp_html.stat().st_size == 0):
        fallback_profile_html(temp_json, temp_html, profile)
        renderer_status = "fallback_html"

    if command_failed and not temp_json.exists():
        cleanup_paths(temp_json, temp_html)
        raise RuntimeError("profile builder failed before producing profile JSON")

    if not temp_json.exists() or temp_json.stat().st_size == 0:
        cleanup_paths(temp_json, temp_html)
        raise RuntimeError("profile report JSON was not created")
    if not temp_html.exists() or temp_html.stat().st_size == 0:
        cleanup_paths(temp_json, temp_html)
        raise RuntimeError("profile report HTML was not created")

    inject_profile_metadata(temp_json, profile)
    annotate_profile_html(temp_html, profile)

    final_json.parent.mkdir(parents=True, exist_ok=True)
    cleanup_paths(final_json, final_html)
    temp_json.replace(final_json)
    temp_html.replace(final_html)
    return renderer_status


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    snapshot_root = repo_root / "data" / "home_snapshots"
    enriched_root = repo_root / "data" / "home_enriched"
    classified_root = repo_root / "data" / "home_classified"
    profile_root = repo_root / "data" / "profile_reports"

    classifier = repo_root / "scripts" / "classification" / "classify_homepage_v2.py"
    enricher = repo_root / "scripts" / "enrichment" / "youtube_enrich.py"
    profile_builder = repo_root / "scripts" / "profile" / "build_profile_report.py"

    for folder in (snapshot_root, enriched_root, classified_root, profile_root):
        folder.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        server_version = "YouTubeLibraryBridge/0.4"

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

            profile = normalize_profile(payload.get("collector_profile"))
            payload["collector_profile"] = profile
            folder_name = profile_folder(profile)

            snapshot_dir = snapshot_root / folder_name
            enriched_dir = enriched_root / folder_name
            classified_dir = classified_root / folder_name
            for folder in (snapshot_dir, enriched_dir, classified_dir):
                folder.mkdir(parents=True, exist_ok=True)

            # One manifest per profile, also kept in the default reports folder.
            profile_manifest = profile_root / f"profile_{profile['profile_short_id']}.identity.json"
            write_json(profile_manifest, profile)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"home_{timestamp}.json"
            stem = Path(filename).stem
            report_stem = f"profile_{profile['profile_short_id']}__{stem}"

            snapshot_path = snapshot_dir / filename
            enriched_path = enriched_dir / filename
            classified_path = classified_dir / filename
            profile_json = profile_root / f"{report_stem}.profile.json"
            profile_html = profile_root / f"{report_stem}.profile.html"

            write_json(snapshot_path, payload)

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
            profile_report_status = "skipped"

            if not args.no_classify:
                try:
                    run_command(
                        [sys.executable, str(classifier), str(classification_input), "--output", str(classified_path)],
                        repo_root,
                    )
                    inject_profile_metadata(classified_path, profile)
                    classified_value = str(classified_path.relative_to(repo_root))
                except subprocess.CalledProcessError as exc:
                    self._json_response(
                        500,
                        {
                            "error": "classification_failed",
                            "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                            "profile_id": profile["profile_id"],
                            "returncode": exc.returncode,
                        },
                    )
                    return

                if not args.no_profile:
                    try:
                        profile_report_status = build_profile_pair(
                            profile_builder=profile_builder,
                            classified_path=classified_path,
                            final_json=profile_json,
                            final_html=profile_html,
                            profile=profile,
                            repo_root=repo_root,
                        )
                        profile_json_value = str(profile_json.relative_to(repo_root))
                        profile_html_value = str(profile_html.relative_to(repo_root))
                    except Exception as exc:
                        profile_report_status = f"failed:{type(exc).__name__}"
                        print(f"Warning: profile report failed: {exc}")

            result = {
                "ok": True,
                "profile_id": profile["profile_id"],
                "profile_short_id": profile["profile_short_id"],
                "profile_label": profile["profile_label"],
                "profile_folder": folder_name,
                "item_count": len(items),
                "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                "enrichment": enrichment_status,
                "classified_path": classified_value,
                "profile_report_status": profile_report_status,
                "profile_json_path": profile_json_value,
                "profile_html_path": profile_html_value,
            }
            print(
                f"[{profile['profile_label']}:{profile['profile_short_id']}] "
                f"Collected {len(items)} videos -> {result['snapshot_path']}"
                + (f" -> {classified_value}" if classified_value else "")
                + (f" -> {profile_json_value}" if profile_json_value else "")
                + (f" -> {profile_html_value}" if profile_html_value else "")
            )
            self._json_response(200, result)

        def log_message(self, format: str, *values: object) -> None:
            print(f"[bridge] {self.address_string()} - {format % values}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"YouTube Library Home Bridge v0.4: http://{args.host}:{args.port}")
    print("Profile identity: extension-local stable ID + user label")
    print("Profile reports: JSON + HTML pair -> data/profile_reports")
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
