#!/usr/bin/env python3
"""Baseline classifier for YouTube homepage snapshots.

Input JSON schema:
{
  "source": "youtube_home",
  "captured_at": "...",
  "items": [
    {
      "video_id": "...",
      "title": "...",
      "channel": "...",
      "url": "...",
      "views_text": "...",
      "published_text": "...",

      // optional enrichment fields
      "description": "...",
      "tags": ["..."],
      "youtube_category_id": 28
    }
  ]
}

The homepage-only baseline uses title + channel. If enrichment fields exist,
they are used automatically and classification_mode becomes "enriched".
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

SOURCE_WEIGHTS = {
    "title": 5.0,
    "channel": 0.5,
    "description": 1.5,
    "tags": 2.5,
}

YOUTUBE_CATEGORY_WEIGHT = 8.0


def normalize(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).lower().strip()


def contains_keyword(text: str, keyword: str) -> bool:
    text = normalize(text)
    keyword = normalize(keyword)
    if not text or not keyword:
        return False
    # Unicode-aware token/phrase boundary. Avoids matching "ai" inside "said".
    pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"
    return re.search(pattern, text) is not None


def keyword_weight(keyword: str) -> float:
    words = keyword.split()
    weight = 1.0 + 0.4 * (len(words) - 1)
    if len(keyword) <= 2:
        weight *= 0.35
    elif len(keyword) <= 4:
        weight *= 0.75
    return weight


def classify_item(item: dict, categories: list[dict]) -> dict:
    scores = {c["id"]: 0.0 for c in categories}
    evidence = {c["id"]: [] for c in categories}

    for category in categories:
        cid = category["id"]
        for source, source_weight in SOURCE_WEIGHTS.items():
            value = item.get(source)
            if not value:
                continue
            values = value if isinstance(value, list) else [value]
            for text in values:
                for keyword in category.get("keywords", []):
                    if contains_keyword(str(text), keyword):
                        added = source_weight * keyword_weight(keyword)
                        scores[cid] += added
                        evidence[cid].append({
                            "source": source,
                            "keyword": keyword,
                            "score": round(added, 3),
                        })

    youtube_category_id = item.get("youtube_category_id")
    if youtube_category_id is not None:
        try:
            youtube_category_id = int(youtube_category_id)
        except (TypeError, ValueError):
            pass
        for category in categories:
            if youtube_category_id in category.get("youtube_video_category_ids", []):
                cid = category["id"]
                scores[cid] += YOUTUBE_CATEGORY_WEIGHT
                evidence[cid].append({
                    "source": "youtube_category_id",
                    "keyword": str(youtube_category_id),
                    "score": YOUTUBE_CATEGORY_WEIGHT,
                })

    positive = {cid: score for cid, score in scores.items() if score > 0}
    enriched = any(item.get(k) for k in ("description", "tags", "youtube_category_id"))
    mode = "enriched" if enriched else "home_visible"

    if not positive:
        return {
            "classification_mode": mode,
            "top_category": None,
            "confidence": "unknown",
            "top_share": 0.0,
            "margin": 0.0,
            "categories": [],
            "evidence": {},
        }

    total = sum(positive.values())
    shares = {cid: score / total for cid, score in positive.items()}
    ranked = sorted(shares.items(), key=lambda x: x[1], reverse=True)
    top_id, top_share = ranked[0]
    second_share = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_share - second_share
    top_raw = scores[top_id]

    if top_raw < 2.0:
        confidence = "unknown"
    elif top_share >= 0.70 and margin >= 0.35:
        confidence = "high"
    elif top_share >= 0.50 and margin >= 0.15:
        confidence = "medium"
    else:
        confidence = "low"

    selected = []
    threshold = max(0.12, top_share * 0.25)
    names = {c["id"]: c.get("name_vi", c["id"]) for c in categories}
    for cid, share in ranked:
        if share < threshold:
            continue
        selected.append({
            "id": cid,
            "name_vi": names[cid],
            "share": round(share, 4),
            "raw_score": round(scores[cid], 3),
        })

    return {
        "classification_mode": mode,
        "top_category": top_id,
        "confidence": confidence,
        "top_share": round(top_share, 4),
        "margin": round(margin, 4),
        "categories": selected,
        "evidence": {cid: evidence[cid] for cid, _ in ranked if evidence[cid]},
    }


def summarize(results: list[dict]) -> dict:
    confidence = Counter(r["classification"]["confidence"] for r in results)
    top_categories = Counter(
        r["classification"]["top_category"]
        for r in results
        if r["classification"]["top_category"]
    )
    margins = [r["classification"]["margin"] for r in results]
    n = len(results)
    return {
        "video_count": n,
        "confidence_counts": dict(confidence),
        "high_medium_rate": round(
            (confidence.get("high", 0) + confidence.get("medium", 0)) / n, 4
        ) if n else 0.0,
        "ambiguous_or_unknown_rate": round(
            (confidence.get("low", 0) + confidence.get("unknown", 0)) / n, 4
        ) if n else 0.0,
        "average_margin": round(sum(margins) / n, 4) if n else 0.0,
        "top_category_distribution": dict(top_categories),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Homepage snapshot JSON")
    parser.add_argument(
        "--dictionary",
        default="taxonomy/homepage_categories.v1.json",
        help="Category dictionary JSON",
    )
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    dictionary = json.loads(Path(args.dictionary).read_text(encoding="utf-8"))
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    categories = dictionary["categories"]

    results = []
    for item in payload.get("items", []):
        results.append({
            **item,
            "classification": classify_item(item, categories),
        })

    output = {
        "source": payload.get("source", "youtube_home"),
        "captured_at": payload.get("captured_at"),
        "dictionary_version": dictionary.get("version"),
        "summary": summarize(results),
        "items": results,
    }

    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
