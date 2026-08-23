#!/usr/bin/env python3
"""Automated read-only YouTube Home collector.

This script opens YouTube Home in a persistent Chrome profile, scrolls the page,
collects rendered video cards, writes a JSON snapshot, and can optionally run
the existing classifier.

It does NOT click/play videos, like, subscribe, comment, or create interactions.

First-time setup:
    pip install playwright
    python scripts/homepage/collect_homepage.py --login

Recurring collection + classification:
    python scripts/homepage/collect_homepage.py --scrolls 8 --classify
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Missing dependency: playwright")
    print("Install it with: pip install playwright")
    raise SystemExit(2)


EXTRACT_JS = r"""
() => {
  const CARD_SELECTORS = [
    'ytd-rich-item-renderer',
    'ytd-video-renderer',
    'ytd-grid-video-renderer',
    'yt-lockup-view-model'
  ];

  const TITLE_SELECTORS = [
    'a#video-title-link[href*="/watch?v="]',
    'a#video-title[href*="/watch?v="]',
    'h3 a[href*="/watch?v="]',
    '.yt-lockup-metadata-view-model-wiz__title a[href*="/watch?v="]',
    'a.yt-lockup-metadata-view-model-wiz__title[href*="/watch?v="]'
  ];

  const CHANNEL_SELECTORS = [
    'ytd-channel-name a',
    '#channel-name a',
    '#text.ytd-channel-name',
    'a[href^="/@"]',
    '.yt-lockup-metadata-view-model-wiz__metadata a[href^="/@"]'
  ];

  const METADATA_SELECTORS = [
    '#metadata-line',
    '#metadata',
    '.yt-content-metadata-view-model-wiz__metadata-text',
    '.yt-lockup-metadata-view-model-wiz__metadata'
  ];

  const DURATION_SELECTORS = [
    'ytd-thumbnail-overlay-time-status-renderer span',
    '#time-status span',
    '.badge-shape-wiz__text'
  ];

  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };

  const firstText = (root, selectors) => {
    for (const selector of selectors) {
      const el = root?.querySelector?.(selector);
      const value = el?.textContent?.trim();
      if (value) return value;
    }
    return '';
  };

  const cards = Array.from(document.querySelectorAll(CARD_SELECTORS.join(',')));
  const items = [];

  for (const card of cards) {
    if (!isVisible(card)) continue;

    let titleAnchor = null;
    for (const selector of TITLE_SELECTORS) {
      const candidate = card.querySelector(selector);
      if (candidate && isVisible(candidate)) {
        titleAnchor = candidate;
        break;
      }
    }
    if (!titleAnchor) continue;

    let url;
    try {
      url = new URL(titleAnchor.href, location.origin);
    } catch {
      continue;
    }

    const videoId = url.searchParams.get('v');
    if (!videoId) continue;

    const title =
      titleAnchor.getAttribute('title')?.trim() ||
      titleAnchor.textContent?.trim() ||
      '';

    if (!title || /^(xem|trực tiếp|live)$/i.test(title) || /^\d{1,2}:\d{2}(?::\d{2})?$/.test(title)) {
      continue;
    }

    items.push({
      video_id: videoId,
      title,
      channel: firstText(card, CHANNEL_SELECTORS),
      url: `https://www.youtube.com/watch?v=${videoId}`,
      metadata_text: firstText(card, METADATA_SELECTORS),
      duration_text: firstText(card, DURATION_SELECTORS)
    });
  }

  return items;
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        default="data/browser_profile",
        help="Persistent browser profile directory (default: data/browser_profile)",
    )
    parser.add_argument(
        "--scrolls",
        type=int,
        default=6,
        help="Number of Home page scroll steps (default: 6)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds to wait after each scroll (default: 1.5)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Snapshot output path; auto-generated when omitted",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Run classify_homepage.py after collection",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open the persistent profile for first-time YouTube login, then exit",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless (not recommended for first-time setup)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    profile_dir = (repo_root / args.profile).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if args.output:
        snapshot_path = Path(args.output)
        if not snapshot_path.is_absolute():
            snapshot_path = repo_root / snapshot_path
    else:
        snapshot_path = repo_root / "data" / "home_snapshots" / f"home_{timestamp}.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=args.headless,
            viewport={"width": 1440, "height": 1000},
            locale="vi-VN",
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        if args.login:
            print("Chrome đã mở với profile riêng của collector.")
            print("Hãy đăng nhập YouTube trong cửa sổ Chrome này nếu cần.")
            input("Đăng nhập xong, quay lại terminal và nhấn Enter để lưu session... ")
            context.close()
            print(f"Đã lưu browser profile tại: {profile_dir}")
            return

        collected: dict[str, dict] = {}

        def collect_visible() -> None:
            try:
                visible_items = page.evaluate(EXTRACT_JS)
            except Exception as exc:
                print(f"Warning: extract failed: {exc}")
                return
            for item in visible_items or []:
                video_id = item.get("video_id")
                if video_id and video_id not in collected:
                    collected[video_id] = item

        collect_visible()
        print(f"Initial cards: {len(collected)}")

        for index in range(max(0, args.scrolls)):
            page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 0.90))")
            time.sleep(max(0.1, args.delay))
            collect_visible()
            print(f"Scroll {index + 1}/{args.scrolls}: {len(collected)} unique videos")

        items = list(collected.values())
        for position, item in enumerate(items, start=1):
            item["position"] = position

        payload = {
            "source": "youtube_home",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "page_url": page.url,
            "item_count": len(items),
            "items": items,
        }

        snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        context.close()

    print(f"Saved {len(items)} videos -> {snapshot_path}")

    if not items:
        print("No valid video cards were captured. YouTube DOM may have changed or Home did not load.")
        return

    if args.classify:
        classified_dir = repo_root / "data" / "home_classified"
        classified_dir.mkdir(parents=True, exist_ok=True)
        classified_path = classified_dir / snapshot_path.name
        classifier = repo_root / "scripts" / "classification" / "classify_homepage.py"
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
        print(f"Classified output -> {classified_path}")


if __name__ == "__main__":
    main()
