#!/usr/bin/env python3
"""Build profile intelligence from a classified YouTube recommendation snapshot.

The output is a probabilistic PRIOR inferred from recommendation exposure, not
confirmed watch behavior. It is designed to work for cold-start/new profiles and
be updated later with behavior and additional recommendation surfaces (e.g. Up Next).

Outputs:
- predicted interest weights
- core / adjacent / exploration recommendation zones
- content direction opportunities
- keyword map and creator-tag map
- expansion candidate videos
- uncertainty / evidence diagnostics
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import unicodedata
import urllib.parse
from collections import defaultdict
from pathlib import Path

CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.2}
INTENT_NAMES = {
    "tutorial": "Hướng dẫn",
    "review": "Đánh giá/Review",
    "news": "Tin tức",
    "livestream": "Phát trực tiếp",
    "compilation": "Tổng hợp/Playlist",
    "documentary": "Tài liệu",
    "entertainment": "Giải trí/Show",
    "analysis": "Phân tích/Bình luận",
}


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", text).strip()


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


def freshness_signal(age_days: object) -> float:
    try:
        days = max(0.0, float(age_days))
    except (TypeError, ValueError):
        return 0.30
    return max(0.15, min(1.0, 1.0 / (1.0 + math.log10(1.0 + days))))


def tag_consistency(tag: str, item: dict) -> float:
    """Lightweight consistency check: downweight tags unsupported by visible metadata."""
    key = normalize_text(tag).lstrip("#")
    if not key:
        return 0.0

    title = normalize_text(item.get("title"))
    description = normalize_text(item.get("description"))
    content = f"{title} {description}".strip()

    if key in content:
        return 1.0

    tokens = [t for t in re.findall(r"\w+", key, flags=re.UNICODE) if len(t) >= 3]
    if tokens:
        overlap = sum(1 for token in tokens if token in content) / len(tokens)
        if overlap >= 0.75:
            return 0.85
        if overlap >= 0.40:
            return 0.65

    topics = " ".join(topic_label(x) for x in (item.get("youtube_topics") or []))
    if tokens and any(token in normalize_text(topics) for token in tokens):
        return 0.70
    return 0.40


def extract_hashtags(item: dict) -> list[str]:
    text = f"{item.get('title') or ''}\n{item.get('description') or ''}"
    found = re.findall(r"(?<!\w)#([\w-]{2,64})", text, flags=re.UNICODE)
    result = []
    seen = set()
    for value in found:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def topic_label(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    tail = text.rsplit("/", 1)[-1]
    return urllib.parse.unquote(tail).replace("_", " ").strip()


def evidence_phrases(item: dict, category_id: str) -> list[str]:
    classification = item.get("classification") or {}
    rows = (classification.get("evidence") or {}).get(category_id) or []
    result = []
    seen = set()
    for row in rows:
        phrase = str(row.get("phrase") or "").strip()
        if not phrase or phrase.isdigit():
            continue
        key = normalize_text(phrase)
        if key not in seen:
            seen.add(key)
            result.append(phrase)
    return result


def effective_categories(item: dict) -> list[dict]:
    """Blend content classification with creator-target metadata when enrichment exists.

    Content remains dominant. Target metadata is a secondary semantic correction,
    useful when broad official YouTube categories (e.g. People & Blogs) are weak.
    """
    combined: dict[str, dict] = {}
    classification = item.get("classification") or {}
    for row in classification.get("categories") or []:
        cid = row.get("id")
        if not cid:
            continue
        combined.setdefault(cid, {"id": cid, "name_vi": row.get("name_vi") or cid, "score": 0.0})
        combined[cid]["score"] += 0.78 * float(row.get("share") or 0.0)

    target = item.get("target_profile") or {}
    if target.get("available"):
        for row in target.get("categories") or []:
            cid = row.get("id")
            if not cid:
                continue
            combined.setdefault(cid, {"id": cid, "name_vi": row.get("name_vi") or cid, "score": 0.0})
            combined[cid]["score"] += 0.22 * float(row.get("share") or 0.0)

    total = sum(x["score"] for x in combined.values())
    if total <= 0:
        return []
    rows = []
    for row in combined.values():
        rows.append({
            "id": row["id"],
            "name_vi": row["name_vi"],
            "share": row["score"] / total,
        })
    rows.sort(key=lambda x: x["share"], reverse=True)
    return rows


def effective_intents(item: dict) -> list[dict]:
    """Remove known weak intent evidence while preserving the classifier output."""
    profile = item.get("intent_profile") or {}
    evidence = profile.get("evidence") or {}
    rows = []
    for row in profile.get("intents") or []:
        iid = row.get("id")
        if not iid:
            continue
        if iid == "news":
            news_evidence = evidence.get("news") or []
            useful = [
                x for x in news_evidence
                if normalize_text(x.get("phrase")) not in {"ngày", "ngày "}
            ]
            if news_evidence and not useful:
                continue
        rows.append(dict(row))

    total = sum(float(x.get("share") or 0.0) for x in rows)
    if total > 0:
        for row in rows:
            row["share"] = float(row.get("share") or 0.0) / total
    return rows


def add_ranked(bucket: dict[str, dict], value: str, score: float, *, source: str, video_id: str, consistency: float = 1.0) -> None:
    display = str(value or "").strip()
    key = normalize_text(display).lstrip("#")
    if not key or len(key) < 2:
        return
    row = bucket.setdefault(key, {
        "value": display.lstrip("#"),
        "score": 0.0,
        "sources": defaultdict(float),
        "video_ids": set(),
        "consistency_weighted": 0.0,
        "consistency_base": 0.0,
    })
    row["score"] += score
    row["sources"][source] += score
    if video_id:
        row["video_ids"].add(video_id)
    row["consistency_weighted"] += consistency * score
    row["consistency_base"] += score


def finalize_ranked(bucket: dict[str, dict], limit: int = 20) -> list[dict]:
    rows = []
    for row in bucket.values():
        base = row["consistency_base"]
        consistency = row["consistency_weighted"] / base if base > 0 else 0.0
        rows.append({
            "value": row["value"],
            "score": round(row["score"], 4),
            "video_support": len(row["video_ids"]),
            "consistency": round(consistency, 4),
            "sources": {k: round(v, 4) for k, v in sorted(row["sources"].items())},
        })
    rows.sort(key=lambda x: (x["score"], x["video_support"], x["consistency"]), reverse=True)
    return rows[:limit]


def build_profile(payload: dict) -> dict:
    items = payload.get("items") or []
    n = len(items)

    category_scores: dict[str, float] = defaultdict(float)
    category_names: dict[str, str] = {}
    category_demand_num: dict[str, float] = defaultdict(float)
    category_fresh_num: dict[str, float] = defaultdict(float)
    category_quality_num: dict[str, float] = defaultdict(float)
    category_base: dict[str, float] = defaultdict(float)
    category_intents: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    category_tags: dict[str, dict[str, dict]] = defaultdict(dict)
    category_keywords: dict[str, dict[str, dict]] = defaultdict(dict)
    category_videos: dict[str, list[dict]] = defaultdict(list)

    global_tags: dict[str, dict] = {}
    global_keywords: dict[str, dict] = {}

    classified_count = 0
    enriched_count = 0
    confidence_sum = 0.0

    per_video = []

    for index, item in enumerate(items, start=1):
        position = int(item.get("position") or index)
        rank = position_weight(position)
        classification = item.get("classification") or {}
        confidence = str(classification.get("confidence") or "unknown")
        conf_w = CONFIDENCE_WEIGHT.get(confidence, 0.2)
        confidence_sum += conf_w
        categories = effective_categories(item)

        if confidence != "unknown" and categories:
            classified_count += 1
        if classification.get("classification_mode") == "enriched":
            enriched_count += 1

        pop = item.get("popularity_profile") or {}
        demand = float(pop.get("demand_signal") or 0.0) if pop.get("available") else 0.25
        fresh = freshness_signal(pop.get("age_days"))
        intents = effective_intents(item)
        video_id = str(item.get("video_id") or "")

        top_category = categories[0].get("id") if categories else None
        per_video.append({
            "video_id": video_id,
            "position": position,
            "title": item.get("title") or "",
            "top_category": top_category,
            "confidence": confidence,
            "rank_weight": rank,
            "demand_signal": demand,
            "freshness_signal": fresh,
        })

        for category in categories:
            cid = category.get("id")
            if not cid:
                continue
            share = float(category.get("share") or 0.0)
            category_names[cid] = category.get("name_vi") or cid
            contribution = share * rank * conf_w
            if contribution <= 0:
                continue

            category_scores[cid] += contribution
            category_base[cid] += contribution
            category_demand_num[cid] += contribution * demand
            category_fresh_num[cid] += contribution * fresh
            category_quality_num[cid] += contribution * conf_w

            for intent in intents:
                iid = intent.get("id")
                if iid:
                    category_intents[cid][iid] += contribution * float(intent.get("share") or 0.0)

            category_videos[cid].append({
                "video_id": video_id,
                "position": position,
                "title": item.get("title") or "",
                "contribution": contribution,
                "demand_signal": round(demand, 4),
                "age_days": pop.get("age_days"),
                "view_count": pop.get("view_count"),
            })

            for tag in item.get("tags") or []:
                consistency = tag_consistency(str(tag), item)
                adjusted = contribution * (0.40 + 0.60 * consistency)
                add_ranked(category_tags[cid], str(tag), adjusted, source="creator_tag", video_id=video_id, consistency=consistency)
                add_ranked(category_keywords[cid], str(tag), adjusted, source="creator_tag", video_id=video_id, consistency=consistency)
                add_ranked(global_tags, str(tag), adjusted, source="creator_tag", video_id=video_id, consistency=consistency)
                add_ranked(global_keywords, str(tag), adjusted, source="creator_tag", video_id=video_id, consistency=consistency)

            for hashtag in extract_hashtags(item):
                score = contribution * 0.80
                add_ranked(category_keywords[cid], hashtag, score, source="hashtag", video_id=video_id)
                add_ranked(global_keywords, hashtag, score, source="hashtag", video_id=video_id)

            for topic in item.get("youtube_topics") or []:
                label = topic_label(topic)
                if label:
                    score = contribution * 1.15
                    add_ranked(category_keywords[cid], label, score, source="youtube_topic", video_id=video_id)
                    add_ranked(global_keywords, label, score, source="youtube_topic", video_id=video_id)

            for phrase in evidence_phrases(item, cid):
                score = contribution * 1.20
                add_ranked(category_keywords[cid], phrase, score, source="classifier_evidence", video_id=video_id)
                add_ranked(global_keywords, phrase, score, source="classifier_evidence", video_id=video_id)

    category_dist = normalize_distribution(category_scores)
    ordered = sorted(category_dist.items(), key=lambda x: x[1], reverse=True)
    top_share = ordered[0][1] if ordered else 0.0
    diversity = normalized_entropy(category_dist)
    top3_share = sum(v for _, v in ordered[:3])

    if not ordered:
        archetype = "Insufficient signal"
    elif top_share >= 0.50 and diversity < 0.55:
        archetype = f"Specialist — {category_names.get(ordered[0][0], ordered[0][0])}"
    elif top_share >= 0.28 and diversity >= 0.65:
        archetype = f"{category_names.get(ordered[0][0], ordered[0][0])}-heavy Variety / Explorer"
    elif diversity >= 0.75:
        archetype = "Variety / Explorer"
    else:
        archetype = "Mixed-interest"

    core_ids = set()
    adjacent_ids = set()
    for idx, (cid, share) in enumerate(ordered):
        if idx == 0 or share >= max(0.20, top_share * 0.55):
            core_ids.add(cid)
        elif share >= max(0.07, top_share * 0.22):
            adjacent_ids.add(cid)

    predicted_interest_weights = []
    content_directions = []

    for cid, share in ordered:
        base = category_base[cid] or 1.0
        demand = category_demand_num[cid] / base
        fresh = category_fresh_num[cid] / base
        quality = category_quality_num[cid] / base
        relative_fit = share / top_share if top_share else 0.0

        if cid in core_ids:
            zone = "core"
        elif cid in adjacent_ids:
            zone = "adjacent"
        else:
            zone = "exploration"

        predicted_interest_weights.append({
            "id": cid,
            "name_vi": category_names.get(cid, cid),
            "predicted_weight": round(share, 4),
            "zone": zone,
            "demand_signal": round(demand, 4),
            "freshness_signal": round(fresh, 4),
        })

        intent_dist = normalize_distribution(category_intents[cid])
        top_intents = [
            {
                "id": iid,
                "name_vi": INTENT_NAMES.get(iid, iid),
                "share": round(value, 4),
            }
            for iid, value in sorted(intent_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

        keywords = finalize_ranked(category_keywords[cid], 15)
        tags = finalize_ranked(category_tags[cid], 15)
        avg_tag_consistency = (
            sum(x["consistency"] * x["score"] for x in tags) / sum(x["score"] for x in tags)
            if tags and sum(x["score"] for x in tags) > 0
            else 0.50
        )
        metadata_coherence = max(0.0, min(1.0, 0.70 * quality + 0.30 * avg_tag_consistency))
        opportunity = (
            0.50 * relative_fit
            + 0.25 * demand
            + 0.10 * fresh
            + 0.15 * metadata_coherence
        )

        sample_videos = sorted(category_videos[cid], key=lambda x: x["contribution"], reverse=True)[:4]
        for row in sample_videos:
            row.pop("contribution", None)

        intent_name = top_intents[0]["name_vi"] if top_intents else None
        direction_name = category_names.get(cid, cid)
        if intent_name:
            direction_name = f"{direction_name} · {intent_name}"

        content_directions.append({
            "id": cid,
            "direction": direction_name,
            "zone": zone,
            "predicted_weight": round(share, 4),
            "relative_profile_fit": round(relative_fit, 4),
            "demand_signal": round(demand, 4),
            "freshness_signal": round(fresh, 4),
            "metadata_coherence": round(metadata_coherence, 4),
            "opportunity_score": round(max(0.0, min(1.0, opportunity)), 4),
            "top_intents": top_intents,
            "keywords": keywords,
            "suggested_tags": tags,
            "sample_videos": sample_videos,
        })

    content_directions.sort(key=lambda x: x["opportunity_score"], reverse=True)

    expansion_candidates = []
    for row in per_video:
        cid = row["top_category"]
        if not cid or cid in core_ids:
            continue
        zone = "adjacent" if cid in adjacent_ids else "exploration"
        expansion_score = row["rank_weight"] * (0.65 + 0.25 * row["demand_signal"] + 0.10 * row["freshness_signal"])
        expansion_candidates.append({
            "video_id": row["video_id"],
            "position": row["position"],
            "title": row["title"],
            "category_id": cid,
            "category_name_vi": category_names.get(cid, cid),
            "zone": zone,
            "expansion_score": round(expansion_score, 4),
            "demand_signal": round(row["demand_signal"], 4),
        })
    expansion_candidates.sort(key=lambda x: x["expansion_score"], reverse=True)

    sample_factor = min(1.0, n / 50.0) if n else 0.0
    classified_rate = classified_count / n if n else 0.0
    enriched_rate = enriched_count / n if n else 0.0
    avg_confidence = confidence_sum / n if n else 0.0
    raw_certainty = 0.25 * sample_factor + 0.30 * classified_rate + 0.25 * enriched_rate + 0.20 * avg_confidence
    certainty = min(0.75, raw_certainty)
    uncertainty = 1.0 - certainty

    return {
        "analysis_version": "1.0.0",
        "profile_type": "recommendation_prior",
        "model_stage": "exposure_only_prior",
        "source": payload.get("source"),
        "source_surfaces": ["home"] if payload.get("source") == "youtube_home" else [payload.get("source")],
        "captured_at": payload.get("captured_at"),
        "classifier_version": payload.get("classifier_version"),
        "video_count": n,
        "archetype": archetype,
        "diversity_score": round(diversity, 4),
        "top3_concentration": round(top3_share, 4),
        "evidence_quality": {
            "classified_count": classified_count,
            "classified_rate": round(classified_rate, 4),
            "enriched_count": enriched_count,
            "enriched_rate": round(enriched_rate, 4),
            "average_confidence_weight": round(avg_confidence, 4),
            "certainty_score": round(certainty, 4),
            "uncertainty_score": round(uncertainty, 4),
            "behavior_evidence_available": False,
        },
        "predicted_interest_weights": predicted_interest_weights,
        "recommendation_zones": {
            "core": [x for x in predicted_interest_weights if x["zone"] == "core"],
            "adjacent": [x for x in predicted_interest_weights if x["zone"] == "adjacent"],
            "exploration": [x for x in predicted_interest_weights if x["zone"] == "exploration"],
        },
        "content_directions": content_directions,
        "expansion_candidates": expansion_candidates[:12],
        "keyword_map": finalize_ranked(global_keywords, 40),
        "creator_tag_map": finalize_ranked(global_tags, 40),
        "interpretation": {
            "predicted_weight": "Heuristic probability-like weight inferred from recommendation exposure; it is not confirmed viewer preference.",
            "zone_core": "Content families repeatedly/strongly represented in the current recommendation surface.",
            "zone_adjacent": "Nearby content families that may share audience context with the core.",
            "zone_exploration": "Lower-weight hypotheses that YouTube may be testing or broadening toward.",
            "opportunity_score": "Heuristic blend of relative profile fit, demand, freshness and metadata coherence. It does not guarantee impressions or views.",
            "suggested_tags": "Observed creator tags associated with a direction, downweighted when weakly supported by title/description/topics. They are research signals, not recommendation controls."
        },
        "limitations": [
            "This is a recommendation-exposure prior, not watch-history truth.",
            "A new/cold-start profile can still have a prior because YouTube exposes an initial set of recommendations.",
            "Without click/watch/skip/completion evidence, interest weights remain uncertain and certainty is capped.",
            "A single Home snapshot cannot prove whether a non-core video is intentional exploration; expansion labels are hypotheses.",
            "Future surfaces such as Up Next / Next video should be added as separate evidence sources rather than mixed silently with Home."
        ]
    }


def pct(value: object) -> float:
    try:
        return float(value) * 100.0
    except (TypeError, ValueError):
        return 0.0


def render_html(profile: dict) -> str:
    interests = profile["predicted_interest_weights"]
    directions = profile["content_directions"]
    keywords = profile["keyword_map"]
    tags = profile["creator_tag_map"]
    expansions = profile["expansion_candidates"]

    def bars(rows: list[dict]) -> str:
        if not rows:
            return '<p class="muted">Chưa đủ dữ liệu.</p>'
        parts = []
        for row in rows:
            label = html.escape(str(row.get("name_vi") or row.get("id")))
            width = max(1.0, pct(row.get("predicted_weight")))
            zone = html.escape(str(row.get("zone") or ""))
            parts.append(
                f'<div class="bar-row"><div class="bar-label"><span>{label} <em>{zone}</em></span>'
                f'<strong>{pct(row.get("predicted_weight")):.1f}%</strong></div>'
                f'<div class="track"><div class="fill" style="width:{width:.2f}%"></div></div></div>'
            )
        return "".join(parts)

    def chips(rows: list[dict], limit: int = 24) -> str:
        if not rows:
            return '<span class="muted">Chưa đủ dữ liệu.</span>'
        return "".join(
            f'<span class="chip">{html.escape(str(row["value"]))}</span>'
            for row in rows[:limit]
        )

    direction_cards = []
    for row in directions[:8]:
        kws = ", ".join(html.escape(x["value"]) for x in row["keywords"][:7])
        tag_text = ", ".join(html.escape(x["value"]) for x in row["suggested_tags"][:7])
        direction_cards.append(
            '<article class="card">'
            f'<div class="eyebrow">{html.escape(row["zone"])} · predicted {pct(row["predicted_weight"]):.1f}%</div>'
            f'<h3>{html.escape(row["direction"])}</h3>'
            f'<div class="score">Opportunity <strong>{row["opportunity_score"]:.2f}</strong></div>'
            f'<p><b>Keywords:</b> {kws or "—"}</p>'
            f'<p><b>Observed tags:</b> {tag_text or "—"}</p>'
            '</article>'
        )

    expansion_rows = "".join(
        f'<tr><td>#{row["position"]}</td><td>{html.escape(row["title"])}</td>'
        f'<td>{html.escape(row["category_name_vi"])}</td><td>{row["expansion_score"]:.2f}</td></tr>'
        for row in expansions[:10]
    )

    eq = profile["evidence_quality"]
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube Profile Intelligence</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }}
body {{ margin:0; background:#101114; color:#f4f5f7; }}
main {{ max-width:1120px; margin:auto; padding:28px 18px 54px; }}
.hero,.panel,.card {{ background:#17191e; border:1px solid #30333a; border-radius:18px; }}
.hero {{ padding:24px; }} .panel {{ padding:20px; margin-top:18px; }}
h1,h2,h3 {{ margin:.2em 0 .55em; }} .muted {{ color:#aeb3bd; line-height:1.55; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-top:18px; }}
.stat {{ background:#20232a; border-radius:14px; padding:14px; }} .stat strong {{ display:block; font-size:1.45rem; margin-top:4px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px; }}
.card {{ padding:16px; }} .eyebrow {{ color:#aeb3bd; font-size:.8rem; text-transform:uppercase; }}
.score {{ margin:8px 0; }} .bar-row {{ margin:13px 0; }}
.bar-label {{ display:flex; justify-content:space-between; gap:12px; font-size:.92rem; }}
.bar-label em {{ font-size:.72rem; color:#aeb3bd; font-style:normal; margin-left:5px; }}
.track {{ height:10px; background:#2a2e36; border-radius:999px; overflow:hidden; margin-top:5px; }}
.fill {{ height:100%; background:linear-gradient(90deg,#8da2fb,#b692f6); border-radius:999px; }}
.chip {{ display:inline-block; padding:7px 10px; margin:4px; background:#242832; border-radius:999px; font-size:.86rem; }}
table {{ width:100%; border-collapse:collapse; font-size:.88rem; }} th,td {{ text-align:left; border-bottom:1px solid #2d3037; padding:10px 7px; vertical-align:top; }}
.note {{ border-left:4px solid #8da2fb; }} ul {{ color:#c7cad1; line-height:1.55; }}
@media(max-width:760px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main>
<section class="hero">
  <div class="muted">Recommendation Prior · Home exposure</div>
  <h1>{html.escape(profile["archetype"])}</h1>
  <p class="muted">Đây là dự đoán từ những gì YouTube đang hiển thị cho profile, không phải khẳng định về lịch sử xem. Trọng số sẽ được cập nhật dần khi có thêm snapshot, hành vi và các surface như Up Next.</p>
  <div class="stats">
    <div class="stat">Video<strong>{profile["video_count"]}</strong></div>
    <div class="stat">Certainty<strong>{pct(eq["certainty_score"]):.1f}%</strong></div>
    <div class="stat">Uncertainty<strong>{pct(eq["uncertainty_score"]):.1f}%</strong></div>
    <div class="stat">Diversity<strong>{profile["diversity_score"]:.2f}</strong></div>
  </div>
</section>

<div class="grid">
  <section class="panel"><h2>Trọng số dự đoán</h2>{bars(interests[:12])}</section>
  <section class="panel"><h2>Keyword map</h2>{chips(keywords)}</section>
</div>

<section class="panel"><h2>Hướng nội dung nên thử</h2><div class="cards">{''.join(direction_cards)}</div></section>
<section class="panel"><h2>Creator tags đang xuất hiện quanh profile</h2>{chips(tags)}</section>

<section class="panel">
<h2>Video có khả năng là mở rộng / thăm dò</h2>
<p class="muted">Đây là giả thuyết từ vị trí + category ngoài core + demand/freshness, không phải nhãn nội bộ của YouTube.</p>
<table><thead><tr><th>Pos</th><th>Video</th><th>Nhóm</th><th>Expansion</th></tr></thead><tbody>{expansion_rows}</tbody></table>
</section>

<section class="panel note">
<h2>Cách dùng kết quả</h2>
<ul>
<li><b>Predicted weight</b>: prior của profile ở thời điểm snapshot.</li>
<li><b>Core / adjacent / exploration</b>: vùng nội dung đang được feed thể hiện mạnh, gần core, hoặc đang có khả năng được thử mở rộng.</li>
<li><b>Opportunity score</b>: dùng để ưu tiên chủ đề thử nghiệm, không phải xác suất YouTube chắc chắn phân phối.</li>
<li><b>Keywords / tags</b>: dùng để hiểu semantic/packaging của các video đang được đưa tới profile; không coi tag là nút điều khiển recommendation.</li>
</ul>
</section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Classified/enriched recommendation JSON")
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
    print(f"Profile intelligence JSON -> {json_path}")
    print(f"Profile intelligence HTML -> {html_path}")


if __name__ == "__main__":
    main()
