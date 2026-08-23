#!/usr/bin/env python3
"""Build a recommendation-exposure profile from a classified YouTube Home snapshot.

This is NOT watch-history truth. It summarizes what the current Home feed exposes
to the profile, with a rank discount so higher Home positions count more.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import defaultdict
from pathlib import Path


CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.2}


def position_weight(position: int) -> float:
    return 1.0 / math.log2(max(2, position + 1))


def normalize_distribution(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in values.items()}


def normalized_entropy(distribution: dict[str, float]) -> float:
    probs = [v for v in distribution.values() if v > 0]
    if len(probs) <= 1:
        return 0.0
    value = -sum(p * math.log(p) for p in probs)
    return value / math.log(len(probs))


def build_profile(payload: dict) -> dict:
    category_scores: dict[str, float] = defaultdict(float)
    intent_scores: dict[str, float] = defaultdict(float)
    category_names: dict[str, str] = {}
    classified = 0
    unknown = 0

    for index, item in enumerate(payload.get("items", []), start=1):
        position = int(item.get("position") or index)
        rank_weight = position_weight(position)
        classification = item.get("classification") or {}
        confidence = classification.get("confidence", "unknown")
        confidence_weight = CONFIDENCE_WEIGHT.get(confidence, 0.2)
        categories = classification.get("categories") or []

        if confidence == "unknown":
            unknown += 1
        else:
            classified += 1

        for category in categories:
            cid = category.get("id")
            if not cid:
                continue
            share = float(category.get("share") or 0.0)
            category_names[cid] = category.get("name_vi") or cid
            category_scores[cid] += share * rank_weight * confidence_weight

        intent = item.get("intent_profile") or {}
        for row in intent.get("intents") or []:
            iid = row.get("id")
            if iid:
                intent_scores[iid] += float(row.get("share") or 0.0) * rank_weight

    category_dist = normalize_distribution(category_scores)
    intent_dist = normalize_distribution(intent_scores)
    ordered_categories = sorted(category_dist.items(), key=lambda x: x[1], reverse=True)
    ordered_intents = sorted(intent_dist.items(), key=lambda x: x[1], reverse=True)
    diversity = normalized_entropy(category_dist)
    dominant = ordered_categories[0] if ordered_categories else (None, 0.0)
    top3_share = sum(v for _, v in ordered_categories[:3])

    if not ordered_categories:
        archetype = "Insufficient signal"
    elif dominant[1] >= 0.50 and diversity < 0.55:
        archetype = f"Specialist — {category_names.get(dominant[0], dominant[0])}"
    elif dominant[1] >= 0.28 and diversity >= 0.65:
        archetype = f"{category_names.get(dominant[0], dominant[0])}-heavy Variety / Explorer"
    elif diversity >= 0.75:
        archetype = "Variety / Explorer"
    else:
        archetype = "Mixed-interest"

    return {
        "profile_type": "recommendation_exposure_profile",
        "source": payload.get("source"),
        "captured_at": payload.get("captured_at"),
        "classifier_version": payload.get("classifier_version"),
        "video_count": len(payload.get("items", [])),
        "classified_count": classified,
        "unknown_count": unknown,
        "archetype": archetype,
        "diversity_score": round(diversity, 4),
        "top3_concentration": round(top3_share, 4),
        "category_distribution": [
            {"id": cid, "name_vi": category_names.get(cid, cid), "share": round(share, 4)}
            for cid, share in ordered_categories
        ],
        "intent_distribution": [
            {"id": iid, "share": round(share, 4)}
            for iid, share in ordered_intents
        ],
        "limitations": [
            "This profile summarizes Home recommendation exposure, not confirmed watch behavior.",
            "Actual behavior requires click/watch/skip/completion interaction logs.",
            "Rank discount gives more weight to videos shown nearer the top of Home.",
            "Unknown or low-confidence videos contribute less to the profile."
        ]
    }


def render_html(profile: dict) -> str:
    categories = profile["category_distribution"]
    intents = profile["intent_distribution"]

    def bars(rows: list[dict], label_key: str) -> str:
        if not rows:
            return '<p class="muted">Chưa đủ dữ liệu.</p>'
        parts = []
        for row in rows:
            label = html.escape(str(row.get(label_key) or row.get("id")))
            pct = float(row["share"]) * 100
            parts.append(
                f'<div class="bar-row"><div class="bar-label"><span>{label}</span>'
                f'<strong>{pct:.1f}%</strong></div>'
                f'<div class="track"><div class="fill" style="width:{max(1.0, pct):.2f}%"></div></div></div>'
            )
        return "".join(parts)

    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube Home Profile</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }}
body {{ margin:0; background:#101114; color:#f4f5f7; }}
main {{ max-width:980px; margin:auto; padding:28px 18px 48px; }}
.hero {{ padding:24px; border:1px solid #30333a; border-radius:18px; background:#17191e; }}
h1,h2 {{ margin:.2em 0 .5em; }} .muted {{ color:#aeb3bd; line-height:1.5; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-top:18px; }}
.stat {{ background:#20232a; border-radius:14px; padding:14px; }}
.stat strong {{ display:block; font-size:1.5rem; margin-top:4px; }}
.grid {{ display:grid; grid-template-columns:1.3fr 1fr; gap:18px; margin-top:18px; }}
.panel {{ background:#17191e; border:1px solid #30333a; border-radius:18px; padding:20px; }}
.bar-row {{ margin:13px 0; }} .bar-label {{ display:flex; justify-content:space-between; gap:12px; font-size:.92rem; }}
.track {{ height:10px; background:#2a2e36; border-radius:999px; overflow:hidden; margin-top:5px; }}
.fill {{ height:100%; background:linear-gradient(90deg,#8da2fb,#b692f6); border-radius:999px; }}
.note {{ margin-top:18px; padding:16px 18px; border-left:4px solid #8da2fb; background:#17191e; }}
ul {{ color:#c7cad1; line-height:1.55; }}
@media(max-width:720px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main>
<section class="hero">
  <div class="muted">Recommendation Exposure Profile</div>
  <h1>{html.escape(profile["archetype"])}</h1>
  <p class="muted">Bản đồ này mô tả nội dung mà YouTube Home đang đưa ra cho profile tại snapshot hiện tại — không phải lịch sử xem thực tế.</p>
  <div class="stats">
    <div class="stat">Video Home<strong>{profile["video_count"]}</strong></div>
    <div class="stat">Đã phân loại<strong>{profile["classified_count"]}</strong></div>
    <div class="stat">Diversity<strong>{profile["diversity_score"]:.2f}</strong></div>
    <div class="stat">Top-3 concentration<strong>{profile["top3_concentration"]*100:.1f}%</strong></div>
  </div>
</section>
<div class="grid">
<section class="panel"><h2>Không gian nội dung</h2>{bars(categories[:10], "name_vi")}</section>
<section class="panel"><h2>Kiểu nội dung / intent</h2>{bars(intents[:8], "id")}</section>
</div>
<section class="note">
<strong>Cách đọc</strong>
<ul>
<li>Category dùng position discount: video càng gần đầu Home càng có trọng số cao hơn.</li>
<li>Confidence thấp/unknown bị giảm trọng số.</li>
<li>Để chuyển từ “recommendation exposure” sang “behavior profile” thật, cần log skip/click/watch/completion của robot.</li>
</ul>
</section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Classified v2 JSON")
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--html-output", default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = repo_root / input_path
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    profile = build_profile(payload)

    json_path = Path(args.json_output) if args.json_output else input_path.with_suffix(".profile.json")
    html_path = Path(args.html_output) if args.html_output else input_path.with_suffix(".profile.html")
    if not json_path.is_absolute():
        json_path = repo_root / json_path
    if not html_path.is_absolute():
        html_path = repo_root / html_path

    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(profile), encoding="utf-8")
    print(f"Profile JSON -> {json_path}")
    print(f"Profile HTML -> {html_path}")


if __name__ == "__main__":
    main()
