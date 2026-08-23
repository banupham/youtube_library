#!/usr/bin/env python3
"""Summarize a Phase 6 Viewer Robot JSONL cohort."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def summarize(viewers: list[dict]) -> dict:
    seed_sources = Counter()
    primary = Counter()
    exploration = Counter()
    category_sum: dict[str, float] = defaultdict(float)
    category_presence = Counter()
    pair_counts = Counter()
    exploration_rates = []
    novelty_values = []
    diversity_values = []
    stability_values = []

    for viewer in viewers:
        seed_sources[str(viewer.get("seed_source") or "unknown")] += 1
        interest = viewer.get("interest_model") or {}
        vector = interest.get("category_vector") or {}
        present = [cid for cid, weight in vector.items() if float(weight or 0.0) >= 0.05]
        for cid, weight in vector.items():
            value = float(weight or 0.0)
            category_sum[cid] += value
            if value >= 0.05:
                category_presence[cid] += 1
        for row in interest.get("primary_interests") or []:
            if row.get("id"):
                primary[str(row["id"])] += 1
        for row in interest.get("exploration_interests") or []:
            if row.get("id"):
                exploration[str(row["id"])] += 1
        for index, left in enumerate(sorted(present)):
            for right in sorted(present)[index + 1 :]:
                pair_counts[(left, right)] += 1

        pref = viewer.get("preference_model") or {}
        exploration_rates.append(float(pref.get("exploration_rate") or 0.0))
        novelty_values.append(float(pref.get("novelty_tolerance") or 0.0))
        diversity_values.append(float(pref.get("diversity_preference") or 0.0))
        stability_values.append(float(pref.get("stability_preference") or 0.0))

    count = len(viewers)
    mean_vector = {
        cid: round(value / count, 6)
        for cid, value in category_sum.items()
    } if count else {}
    ordered_mean = sorted(mean_vector.items(), key=lambda item: (-item[1], item[0]))

    return {
        "version": "1.0.0",
        "viewer_count": count,
        "seed_sources": dict(seed_sources),
        "mean_category_vector": [
            {
                "id": cid,
                "mean_weight": weight,
                "presence_rate_ge_5pct": round(category_presence[cid] / count, 6) if count else 0.0,
            }
            for cid, weight in ordered_mean
        ],
        "primary_category_counts": [
            {"id": cid, "count": value, "rate": round(value / count, 6) if count else 0.0}
            for cid, value in primary.most_common()
        ],
        "exploration_category_counts": [
            {"id": cid, "count": value, "rate": round(value / count, 6) if count else 0.0}
            for cid, value in exploration.most_common()
        ],
        "preference_summary": {
            "mean_exploration_rate": round(mean(exploration_rates), 6),
            "mean_novelty_tolerance": round(mean(novelty_values), 6),
            "mean_diversity_preference": round(mean(diversity_values), 6),
            "mean_stability_preference": round(mean(stability_values), 6),
        },
        "top_cointerest_pairs_ge_5pct": [
            {
                "left": pair[0],
                "right": pair[1],
                "viewer_count": value,
                "rate": round(value / count, 6) if count else 0.0,
            }
            for pair, value in pair_counts.most_common(30)
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("viewers_jsonl")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    path = Path(args.viewers_jsonl).resolve()
    viewers = read_jsonl(path)
    result = summarize(viewers)

    if args.output:
        output = Path(args.output).resolve()
    else:
        output = path.parent / "summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Viewer count -> {result['viewer_count']}")
    print(f"Summary -> {output}")
    print("Top primary categories:")
    for row in result["primary_category_counts"][:8]:
        print(f"  {row['id']}: {row['count']} ({row['rate'] * 100:.1f}%)")


if __name__ == "__main__":
    main()
