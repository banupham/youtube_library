#!/usr/bin/env python3
"""Enrich YouTube Home video IDs with public YouTube Data API metadata.

Requires:
    set YOUTUBE_API_KEY=...
    python scripts/enrichment/youtube_enrich.py input.json --output enriched.json

Adds description, tags, youtube_category_id, youtube_topics, published_at and
public statistics. The API key is never written to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


API_URL = "https://www.googleapis.com/youtube/v3/videos"


def chunks(values: list[str], size: int = 50):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def fetch_batch(video_ids: list[str], api_key: str) -> dict[str, dict]:
    params = {
        "part": "snippet,statistics,topicDetails",
        "id": ",".join(video_ids),
        "key": api_key,
        "maxResults": "50",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "youtube-library/0.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = {}
    for video in payload.get("items", []):
        snippet = video.get("snippet") or {}
        stats = video.get("statistics") or {}
        topics = video.get("topicDetails") or {}
        result[video["id"]] = {
            "description": snippet.get("description") or "",
            "tags": snippet.get("tags") or [],
            "youtube_category_id": snippet.get("categoryId"),
            "published_at": snippet.get("publishedAt"),
            "youtube_topics": topics.get("topicCategories") or [],
            "statistics": {
                "view_count": stats.get("viewCount"),
                "like_count": stats.get("likeCount"),
                "comment_count": stats.get("commentCount"),
            },
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Home snapshot JSON")
    parser.add_argument("--output", required=True, help="Enriched output JSON")
    parser.add_argument("--api-key", default=None, help="Override YOUTUBE_API_KEY env var")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.is_absolute():
        input_path = repo_root / input_path
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    api_key = args.api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit("Missing API key. Set YOUTUBE_API_KEY or pass --api-key. The key is never saved by this script.")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    video_ids = list(dict.fromkeys(str(x.get("video_id")) for x in items if x.get("video_id")))

    enrichment: dict[str, dict] = {}
    for batch in chunks(video_ids):
        enrichment.update(fetch_batch(batch, api_key))

    enriched_items = []
    for item in items:
        row = dict(item)
        row.update(enrichment.get(str(item.get("video_id"))) or {})
        enriched_items.append(row)

    output = dict(payload)
    output["enrichment"] = {
        "source": "youtube_data_api_v3",
        "requested_video_count": len(video_ids),
        "enriched_video_count": len(enrichment),
    }
    output["items"] = enriched_items
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Enriched {len(enrichment)}/{len(video_ids)} videos -> {output_path}")


if __name__ == "__main__":
    main()
