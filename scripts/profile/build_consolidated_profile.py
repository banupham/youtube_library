#!/usr/bin/env python3
"""Build one consolidated recommendation-profile report from a collection session.

The report treats Home as the profile-level prior and Up Next as contextual evidence.
Repeated Up Next replays are used to estimate recommendation stability. The output is
an inferred exposure profile for creator research, not YouTube's internal user model
and not a guarantee of impressions or views.
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
from datetime import datetime, timezone
from pathlib import Path

CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.2}
HOME_SURFACE_WEIGHT = 0.62
UPNEXT_SURFACE_WEIGHT = 0.38
INTENT_LABELS = {
    "tutorial": "Tutorial Learner",
    "review": "Review Researcher",
    "news": "News Seeker",
    "livestream": "Live Event Follower",
    "compilation": "Playlist / Compilation Explorer",
    "documentary": "Documentary Learner",
    "entertainment": "Entertainment Explorer",
    "analysis": "Analysis / Commentary Seeker",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", text).strip()


def position_weight(position: object) -> float:
    try:
        p = max(1, int(position))
    except (TypeError, ValueError):
        p = 1
    return 1.0 / math.log2(p + 1)


def normalize_distribution(values: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in values.values() if v > 0)
    if total <= 0:
        return {}
    return {k: max(0.0, v) / total for k, v in values.items() if v > 0}


def topic_label(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    tail = text.rsplit("/", 1)[-1]
    return urllib.parse.unquote(tail).replace("_", " ").strip()


def tag_consistency(tag: str, item: dict) -> float:
    key = norm(tag).lstrip("#")
    if not key:
        return 0.0
    title = norm(item.get("title"))
    description = norm(item.get("description"))
    content = f"{title} {description}".strip()
    if key and key in content:
        return 1.0
    tokens = [x for x in re.findall(r"\w+", key, flags=re.UNICODE) if len(x) >= 3]
    if tokens:
        overlap = sum(1 for token in tokens if token in content) / len(tokens)
        if overlap >= 0.75:
            return 0.85
        if overlap >= 0.40:
            return 0.65
        topics = norm(" ".join(topic_label(x) for x in item.get("youtube_topics") or []))
        if any(token in topics for token in tokens):
            return 0.70
    return 0.40


def item_categories(item: dict) -> list[dict]:
    classification = item.get("classification") or {}
    content = classification.get("categories") or []
    target = (item.get("target_profile") or {}).get("categories") or []
    combined: dict[str, dict] = {}
    for row in content:
        cid = row.get("id")
        if not cid:
            continue
        combined.setdefault(cid, {"id": cid, "name_vi": row.get("name_vi") or cid, "score": 0.0})
        combined[cid]["score"] += 0.85 * float(row.get("share") or 0.0)
    for row in target:
        cid = row.get("id")
        if not cid:
            continue
        combined.setdefault(cid, {"id": cid, "name_vi": row.get("name_vi") or cid, "score": 0.0})
        combined[cid]["score"] += 0.15 * float(row.get("share") or 0.0)
    total = sum(row["score"] for row in combined.values())
    if total <= 0:
        return []
    result = [{"id": row["id"], "name_vi": row["name_vi"], "share": row["score"] / total} for row in combined.values()]
    return sorted(result, key=lambda x: x["share"], reverse=True)


def item_intents(item: dict) -> list[dict]:
    rows = (item.get("intent_profile") or {}).get("intents") or []
    return [row for row in rows if row.get("id")]


def evidence_terms(item: dict, cid: str) -> list[str]:
    evidence = ((item.get("classification") or {}).get("evidence") or {}).get(cid) or []
    out, seen = [], set()
    for row in evidence:
        phrase = str(row.get("phrase") or "").strip()
        if not phrase or phrase.isdigit():
            continue
        key = norm(phrase)
        if key and key not in seen:
            seen.add(key)
            out.append(phrase)
    return out


def add_term(bucket: dict[str, dict], value: str, score: float, surface: str, video_id: str, source: str, consistency: float = 1.0) -> None:
    display = str(value or "").strip().lstrip("#")
    key = norm(display)
    if len(key) < 2 or score <= 0:
        return
    row = bucket.setdefault(key, {
        "value": display,
        "score": 0.0,
        "surfaces": set(),
        "video_ids": set(),
        "sources": defaultdict(float),
        "consistency_num": 0.0,
        "consistency_den": 0.0,
    })
    row["score"] += score
    row["surfaces"].add(surface)
    if video_id:
        row["video_ids"].add(video_id)
    row["sources"][source] += score
    row["consistency_num"] += consistency * score
    row["consistency_den"] += score


def finalize_terms(bucket: dict[str, dict], limit: int, *, min_consistency: float = 0.0) -> list[dict]:
    rows = []
    for row in bucket.values():
        consistency = row["consistency_num"] / row["consistency_den"] if row["consistency_den"] else 0.0
        if consistency < min_consistency:
            continue
        surface_count = len(row["surfaces"])
        boosted = row["score"] * (1.12 if surface_count >= 2 else 1.0)
        rows.append({
            "value": row["value"],
            "score": round(boosted, 4),
            "video_support": len(row["video_ids"]),
            "surface_support": sorted(row["surfaces"]),
            "cross_surface": surface_count >= 2,
            "consistency": round(consistency, 4),
            "sources": {k: round(v, 4) for k, v in sorted(row["sources"].items())},
        })
    rows.sort(key=lambda x: (x["cross_surface"], x["score"], x["video_support"], x["consistency"]), reverse=True)
    return rows[:limit]


def load_entry(repo_root: Path, entry: dict) -> dict | None:
    value = entry.get("classified_path")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        return None
    return read_json(path)


def process_item(
    item: dict,
    weight: float,
    surface: str,
    category_scores: dict[str, float],
    category_names: dict[str, str],
    intent_scores: dict[str, float],
    topic_terms: dict[str, dict],
    keyword_terms: dict[str, dict],
    creator_tags: dict[str, dict],
    category_keywords: dict[str, dict[str, dict]],
    category_tags: dict[str, dict[str, dict]],
    category_demand_num: dict[str, float],
    category_demand_den: dict[str, float],
) -> None:
    if weight <= 0:
        return
    video_id = str(item.get("video_id") or "")
    categories = item_categories(item)
    demand = float((item.get("popularity_profile") or {}).get("demand_signal") or 0.25)
    for category in categories:
        cid = category["id"]
        share = float(category.get("share") or 0.0)
        contribution = weight * share
        category_scores[cid] += contribution
        category_names[cid] = category.get("name_vi") or cid
        category_demand_num[cid] += contribution * demand
        category_demand_den[cid] += contribution

        for phrase in evidence_terms(item, cid):
            add_term(keyword_terms, phrase, contribution * 1.15, surface, video_id, "classifier_evidence")
            add_term(category_keywords[cid], phrase, contribution * 1.15, surface, video_id, "classifier_evidence")

        for tag in item.get("tags") or []:
            consistency = tag_consistency(str(tag), item)
            adjusted = contribution * (0.35 + 0.65 * consistency)
            add_term(keyword_terms, str(tag), adjusted, surface, video_id, "creator_tag", consistency)
            add_term(creator_tags, str(tag), adjusted, surface, video_id, "creator_tag", consistency)
            add_term(category_keywords[cid], str(tag), adjusted, surface, video_id, "creator_tag", consistency)
            add_term(category_tags[cid], str(tag), adjusted, surface, video_id, "creator_tag", consistency)

        for topic in item.get("youtube_topics") or []:
            label = topic_label(topic)
            if label:
                add_term(topic_terms, label, contribution * 1.2, surface, video_id, "youtube_topic")
                add_term(keyword_terms, label, contribution * 1.1, surface, video_id, "youtube_topic")
                add_term(category_keywords[cid], label, contribution * 1.1, surface, video_id, "youtube_topic")

    for intent in item_intents(item):
        intent_scores[intent["id"]] += weight * float(intent.get("share") or 0.0)


def behavior_name(category_name: str, top_intent: str | None, diversity: float, top_share: float) -> str:
    intent_name = INTENT_LABELS.get(top_intent or "", "Explorer")
    if top_share >= 0.34:
        return f"{category_name} · {intent_name}"
    if diversity >= 0.72:
        return f"Multi-interest · {intent_name}"
    return f"{category_name}-leaning · {intent_name}"


def build_profile(repo_root: Path, session: dict) -> dict:
    surfaces = session.get("surfaces") or {}
    home_entries = surfaces.get("home") or []
    up_entries = surfaces.get("up_next") or []

    home_payloads = [x for x in (load_entry(repo_root, entry) for entry in home_entries) if x]
    up_loaded = [(entry, load_entry(repo_root, entry)) for entry in up_entries]
    up_loaded = [(entry, payload) for entry, payload in up_loaded if payload]

    category_names: dict[str, str] = {}
    home_cat: dict[str, float] = defaultdict(float)
    up_cat: dict[str, float] = defaultdict(float)
    home_intent: dict[str, float] = defaultdict(float)
    up_intent: dict[str, float] = defaultdict(float)
    home_topics: dict[str, dict] = {}
    up_topics: dict[str, dict] = {}
    home_keywords: dict[str, dict] = {}
    up_keywords: dict[str, dict] = {}
    home_tags: dict[str, dict] = {}
    up_tags: dict[str, dict] = {}
    category_keywords: dict[str, dict[str, dict]] = defaultdict(dict)
    category_tags: dict[str, dict[str, dict]] = defaultdict(dict)
    category_demand_num: dict[str, float] = defaultdict(float)
    category_demand_den: dict[str, float] = defaultdict(float)

    home_items = 0
    for payload in home_payloads[-1:]:
        items = payload.get("items") or []
        home_items += len(items)
        for idx, item in enumerate(items, start=1):
            confidence = str((item.get("classification") or {}).get("confidence") or "unknown")
            weight = position_weight(item.get("position") or idx) * CONFIDENCE_WEIGHT.get(confidence, 0.2)
            process_item(item, weight, "home", home_cat, category_names, home_intent, home_topics, home_keywords, home_tags,
                         category_keywords, category_tags, category_demand_num, category_demand_den)

    # Up Next: normalize within each seed so many replays do not drown Home.
    by_seed: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for entry, payload in up_loaded:
        seed = str(entry.get("parent_video_id") or payload.get("parent_video_id") or "unknown")
        by_seed[seed].append((entry, payload))

    stable_videos = []
    seed_category_dists: list[dict[str, float]] = []
    seed_intent_dists: list[dict[str, float]] = []
    total_up_items = 0
    replay_total = 0

    for seed, pairs in by_seed.items():
        replay_total += len(pairs)
        seed_cat: dict[str, float] = defaultdict(float)
        seed_intent: dict[str, float] = defaultdict(float)
        occurrences: dict[str, dict] = {}
        replay_count = max(1, len(pairs))

        for _, payload in pairs:
            items = payload.get("items") or []
            total_up_items += len(items)
            seen_replay = set()
            for idx, item in enumerate(items, start=1):
                video_id = str(item.get("video_id") or "")
                confidence = str((item.get("classification") or {}).get("confidence") or "unknown")
                base = position_weight(item.get("position") or idx) * CONFIDENCE_WEIGHT.get(confidence, 0.2) / replay_count
                process_item(item, base, "up_next", seed_cat, category_names, seed_intent, up_topics, up_keywords, up_tags,
                             category_keywords, category_tags, category_demand_num, category_demand_den)
                if video_id and video_id not in seen_replay:
                    seen_replay.add(video_id)
                    row = occurrences.setdefault(video_id, {
                        "video_id": video_id,
                        "title": item.get("title") or "",
                        "channel": item.get("channel") or "",
                        "appearances": 0,
                        "position_sum": 0.0,
                    })
                    row["appearances"] += 1
                    row["position_sum"] += float(item.get("position") or idx)

        seed_cat_norm = normalize_distribution(seed_cat)
        seed_int_norm = normalize_distribution(seed_intent)
        if seed_cat_norm:
            seed_category_dists.append(seed_cat_norm)
        if seed_int_norm:
            seed_intent_dists.append(seed_int_norm)

        for row in occurrences.values():
            appearance_rate = row["appearances"] / replay_count
            stable_videos.append({
                "seed_video_id": seed,
                "video_id": row["video_id"],
                "title": row["title"],
                "channel": row["channel"],
                "appearances": row["appearances"],
                "replay_count": replay_count,
                "appearance_rate": round(appearance_rate, 4),
                "mean_position": round(row["position_sum"] / max(1, row["appearances"]), 2),
            })

    if seed_category_dists:
        for dist in seed_category_dists:
            for cid, value in dist.items():
                up_cat[cid] += value / len(seed_category_dists)
    if seed_intent_dists:
        for dist in seed_intent_dists:
            for iid, value in dist.items():
                up_intent[iid] += value / len(seed_intent_dists)

    home_dist = normalize_distribution(home_cat)
    up_dist = normalize_distribution(up_cat)
    home_intent_dist = normalize_distribution(home_intent)
    up_intent_dist = normalize_distribution(up_intent)

    combined: dict[str, float] = defaultdict(float)
    if home_dist and up_dist:
        for cid, value in home_dist.items():
            combined[cid] += HOME_SURFACE_WEIGHT * value
        for cid, value in up_dist.items():
            combined[cid] += UPNEXT_SURFACE_WEIGHT * value
        for cid in set(home_dist) & set(up_dist):
            combined[cid] *= 1.08
    elif home_dist:
        combined.update(home_dist)
    else:
        combined.update(up_dist)
    combined = normalize_distribution(combined)
    ordered = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    top_share = ordered[0][1] if ordered else 0.0

    intent_combined: dict[str, float] = defaultdict(float)
    if home_intent_dist and up_intent_dist:
        for iid, value in home_intent_dist.items():
            intent_combined[iid] += HOME_SURFACE_WEIGHT * value
        for iid, value in up_intent_dist.items():
            intent_combined[iid] += UPNEXT_SURFACE_WEIGHT * value
    elif home_intent_dist:
        intent_combined.update(home_intent_dist)
    else:
        intent_combined.update(up_intent_dist)
    intent_combined = normalize_distribution(intent_combined)
    top_intent = max(intent_combined, key=intent_combined.get) if intent_combined else None

    probs = [v for _, v in ordered if v > 0]
    diversity = 0.0
    if len(probs) > 1:
        diversity = -sum(p * math.log(p) for p in probs) / math.log(len(probs))

    interests = []
    for idx, (cid, share) in enumerate(ordered):
        if idx == 0 or share >= max(0.18, top_share * 0.55):
            zone = "core"
        elif share >= max(0.065, top_share * 0.22):
            zone = "adjacent"
        else:
            zone = "exploration"
        home_share = home_dist.get(cid, 0.0)
        up_share = up_dist.get(cid, 0.0)
        cross = home_share > 0 and up_share > 0
        demand = category_demand_num[cid] / category_demand_den[cid] if category_demand_den[cid] else 0.25
        relative_fit = share / top_share if top_share else 0.0
        stability_signal = min(1.0, up_share / max(0.001, share)) if up_share else 0.0
        opportunity = 0.58 * relative_fit + 0.20 * demand + 0.14 * stability_signal + 0.08 * (1.0 if cross else 0.35)
        interests.append({
            "id": cid,
            "name_vi": category_names.get(cid, cid),
            "predicted_weight": round(share, 4),
            "zone": zone,
            "home_weight": round(home_share, 4),
            "up_next_weight": round(up_share, 4),
            "cross_surface": cross,
            "demand_signal": round(demand, 4),
            "opportunity_score": round(max(0.0, min(1.0, opportunity)), 4),
            "keywords": finalize_terms(category_keywords[cid], 14),
            "creative_tags": finalize_terms(category_tags[cid], 14, min_consistency=0.55),
        })

    stable_videos.sort(key=lambda x: (x["appearance_rate"], -x["mean_position"]), reverse=True)
    stable_count = sum(1 for row in stable_videos if row["appearance_rate"] >= 0.67)
    stability_ratio = stable_count / len(stable_videos) if stable_videos else 0.0

    merged_keywords: dict[str, dict] = {}
    merged_tags: dict[str, dict] = {}
    merged_topics: dict[str, dict] = {}
    for bucket, destination in ((home_keywords, merged_keywords), (up_keywords, merged_keywords),
                                (home_tags, merged_tags), (up_tags, merged_tags),
                                (home_topics, merged_topics), (up_topics, merged_topics)):
        for key, row in bucket.items():
            target = destination.setdefault(key, {
                "value": row["value"], "score": 0.0, "surfaces": set(), "video_ids": set(),
                "sources": defaultdict(float), "consistency_num": 0.0, "consistency_den": 0.0,
            })
            target["score"] += row["score"]
            target["surfaces"].update(row["surfaces"])
            target["video_ids"].update(row["video_ids"])
            for source, score in row["sources"].items():
                target["sources"][source] += score
            target["consistency_num"] += row["consistency_num"]
            target["consistency_den"] += row["consistency_den"]

    creative_keywords = finalize_terms(merged_keywords, 36, min_consistency=0.45)
    creative_tags = finalize_terms(merged_tags, 30, min_consistency=0.60)
    topic_map = finalize_terms(merged_topics, 24)

    top_category_name = interests[0]["name_vi"] if interests else "Insufficient signal"
    profile_name = behavior_name(top_category_name, top_intent, diversity, top_share)

    phases = []
    if interests:
        anchor = interests[0]
        phases.append({
            "phase": 1,
            "role": "anchor",
            "direction": anchor["name_vi"],
            "recommended_share_of_next_videos": "60-70%",
            "goal": "Củng cố một chuỗi nội dung nhất quán quanh tín hiệu mạnh nhất của profile.",
            "keywords": [x["value"] for x in anchor["keywords"][:8]],
            "tags": [x["value"] for x in anchor["creative_tags"][:8]],
        })
    if len(interests) > 1:
        bridge = next((x for x in interests[1:] if x["cross_surface"]), interests[1])
        phases.append({
            "phase": 2,
            "role": "bridge",
            "direction": bridge["name_vi"],
            "recommended_share_of_next_videos": "20-30%",
            "goal": "Mở rộng bằng nội dung có giao nhau giữa Home và Up Next, không đổi chủ đề đột ngột.",
            "keywords": [x["value"] for x in bridge["keywords"][:8]],
            "tags": [x["value"] for x in bridge["creative_tags"][:8]],
        })
    if len(interests) > 2:
        explore = next((x for x in interests[2:] if x["zone"] == "exploration"), interests[2])
        phases.append({
            "phase": 3,
            "role": "controlled_expansion",
            "direction": explore["name_vi"],
            "recommended_share_of_next_videos": "<=10-15%",
            "goal": "Chỉ thử mở rộng khi tín hiệu lặp lại qua nhiều seed/replay; tránh kênh thành nhiều thể loại rời rạc.",
            "keywords": [x["value"] for x in explore["keywords"][:8]],
            "tags": [x["value"] for x in explore["creative_tags"][:8]],
        })

    sample_factor = min(1.0, (home_items + min(total_up_items, 120)) / 100.0)
    surface_factor = 1.0 if home_items and by_seed else 0.65
    replay_factor = min(1.0, replay_total / max(1, len(by_seed) * 3)) if by_seed else 0.0
    certainty = min(0.82, 0.20 + 0.25 * sample_factor + 0.20 * surface_factor + 0.18 * replay_factor + 0.17 * stability_ratio)

    profile = session.get("profile") or {}
    return {
        "analysis_version": "2.0.0",
        "profile_type": "creator_opportunity_profile",
        "model_stage": "home_plus_up_next_exposure",
        "collection_session_id": session.get("collection_session_id"),
        "profile": profile,
        "behavior_profile_name": profile_name,
        "behavior_profile_name_basis": {
            "top_category": top_category_name,
            "top_intent": top_intent,
            "top_intent_label": INTENT_LABELS.get(top_intent or "", "Explorer"),
            "note": "Tên hồ sơ là nhãn nghiên cứu suy ra từ recommendation exposure, không phải nhãn nội bộ của YouTube.",
        },
        "surface_evidence": {
            "home_items": home_items,
            "up_next_seed_count": len(by_seed),
            "up_next_replay_count": replay_total,
            "up_next_observations": total_up_items,
            "stable_up_next_video_count": stable_count,
            "stable_up_next_ratio": round(stability_ratio, 4),
        },
        "certainty_score": round(certainty, 4),
        "uncertainty_score": round(1.0 - certainty, 4),
        "diversity_score": round(diversity, 4),
        "interest_weights": interests,
        "intent_weights": [
            {"id": iid, "label": INTENT_LABELS.get(iid, iid), "weight": round(value, 4)}
            for iid, value in sorted(intent_combined.items(), key=lambda x: x[1], reverse=True)
        ],
        "topic_map": topic_map,
        "creative_keywords": creative_keywords,
        "creative_tags": creative_tags,
        "stable_up_next": stable_videos[:40],
        "content_series_plan": phases,
        "channel_focus_guardrails": [
            "Duy trì một anchor lane chính; không tối ưu kênh cho nhiều category rời rạc cùng lúc.",
            "Chỉ mở bridge lane khi tín hiệu xuất hiện trên Home và/hoặc lặp lại ở nhiều Up Next seed/replay.",
            "Exploration chỉ nên chiếm tỷ trọng nhỏ cho tới khi nó trở thành tín hiệu lặp lại ổn định.",
            "Keywords/tags dùng để mô tả semantic và packaging của vùng nội dung; không xem chúng là nút điều khiển recommendation.",
            "Ưu tiên chuỗi video liên quan có khả năng dẫn người xem từ một chủ đề sang chủ đề kế cận thay vì pivot đột ngột.",
        ],
        "interpretation": {
            "interest_weights": "Trọng số heuristic kết hợp Home prior và Up Next contextual evidence; không phải xác suất nội bộ của YouTube.",
            "stable_up_next": "Video xuất hiện lặp lại qua replay được coi là neighborhood ổn định hơn; không đồng nghĩa người dùng sẽ xem.",
            "opportunity_score": "Điểm ưu tiên nghiên cứu kết hợp profile fit, demand, Up Next stability và cross-surface support; không đảm bảo impressions/views.",
            "creative_tags": "Tags quan sát từ video đang được hiển thị, lọc theo consistency với nội dung; dùng cho nghiên cứu định vị.",
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def pct(value: object) -> float:
    try:
        return float(value) * 100
    except (TypeError, ValueError):
        return 0.0


def render_html(profile: dict) -> str:
    identity = profile.get("profile") or {}
    interests = profile.get("interest_weights") or []
    phases = profile.get("content_series_plan") or []
    keywords = profile.get("creative_keywords") or []
    tags = profile.get("creative_tags") or []
    stable = profile.get("stable_up_next") or []
    evidence = profile.get("surface_evidence") or {}

    bars = "".join(
        f'<div class="bar"><div><b>{html.escape(str(x["name_vi"]))}</b><span>{html.escape(x["zone"])}</span><strong>{pct(x["predicted_weight"]):.1f}%</strong></div>'
        f'<i><em style="width:{max(1.0,pct(x["predicted_weight"])):.2f}%"></em></i>'
        f'<small>Home {pct(x["home_weight"]):.1f}% · Up Next {pct(x["up_next_weight"]):.1f}% · Opportunity {x["opportunity_score"]:.2f}</small></div>'
        for x in interests[:12]
    )

    cards = "".join(
        '<article>'
        f'<small>Phase {x["phase"]} · {html.escape(x["role"])} · {html.escape(x["recommended_share_of_next_videos"])}</small>'
        f'<h3>{html.escape(x["direction"])}</h3><p>{html.escape(x["goal"])}</p>'
        f'<p><b>Keywords:</b> {html.escape(", ".join(x["keywords"]) or "—")}</p>'
        f'<p><b>Tags:</b> {html.escape(", ".join(x["tags"]) or "—")}</p></article>'
        for x in phases
    )

    keyword_chips = "".join(f'<span>{html.escape(str(x["value"]))}</span>' for x in keywords[:28])
    tag_chips = "".join(f'<span>{html.escape(str(x["value"]))}</span>' for x in tags[:28])
    stable_rows = "".join(
        f'<tr><td>{html.escape(str(x["title"]))}</td><td>{x["appearances"]}/{x["replay_count"]}</td><td>{x["mean_position"]:.1f}</td></tr>'
        for x in stable[:20]
    )

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube Profile Library</title><style>
body{{margin:0;background:#0f1115;color:#f4f6f8;font-family:Inter,system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px 18px 60px}}
.hero,.panel,article{{background:#171a20;border:1px solid #30343d;border-radius:18px}}.hero,.panel{{padding:20px;margin-bottom:16px}}h1,h2,h3{{margin:.2em 0 .6em}}
.muted,small{{color:#aab1bd}}.stats,.grid,.cards{{display:grid;gap:12px}}.stats{{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}}.grid{{grid-template-columns:1fr 1fr}}
.cards{{grid-template-columns:repeat(auto-fit,minmax(270px,1fr))}}.stat,article{{background:#20242c;padding:14px;border-radius:14px}}.stat strong{{display:block;font-size:1.4rem;margin-top:4px}}
.bar{{margin:14px 0}}.bar>div{{display:flex;gap:10px;align-items:center}}.bar span{{color:#aab1bd;font-size:.78rem}}.bar strong{{margin-left:auto}}.bar i{{display:block;height:10px;background:#2b3039;border-radius:999px;overflow:hidden;margin:5px 0}}.bar em{{display:block;height:100%;background:#9aacff;border-radius:999px}}
.chips span{{display:inline-block;padding:7px 10px;margin:4px;background:#252a34;border-radius:999px;font-size:.86rem}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 7px;text-align:left;border-bottom:1px solid #2d323b;font-size:.88rem}}
.note{{border-left:4px solid #9aacff}}ul{{line-height:1.55;color:#c8cdd5}}@media(max-width:780px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="hero"><div class="muted">Profile Library · {html.escape(str(identity.get("profile_label") or "Profile"))} · {html.escape(str(identity.get("profile_short_id") or ""))}</div>
<h1>{html.escape(profile["behavior_profile_name"])}</h1><p class="muted">Hồ sơ nghiên cứu tổng hợp từ Home + Up Next replay. Mục tiêu là chọn chuỗi nội dung có semantic fit tốt với vùng recommendation đang quan sát, không phải mô phỏng nhãn nội bộ của YouTube.</p>
<div class="stats"><div class="stat">Certainty<strong>{pct(profile["certainty_score"]):.1f}%</strong></div><div class="stat">Home items<strong>{evidence.get("home_items",0)}</strong></div><div class="stat">Up Next seeds<strong>{evidence.get("up_next_seed_count",0)}</strong></div><div class="stat">Replays<strong>{evidence.get("up_next_replay_count",0)}</strong></div><div class="stat">Stable ratio<strong>{pct(evidence.get("stable_up_next_ratio",0)):.1f}%</strong></div></div></section>
<div class="grid"><section class="panel"><h2>Trọng số hồ sơ</h2>{bars or '<p class="muted">Chưa đủ dữ liệu.</p>'}</section><section class="panel"><h2>Creative keywords</h2><div class="chips">{keyword_chips or '—'}</div><h2>Creative tags</h2><div class="chips">{tag_chips or '—'}</div></section></div>
<section class="panel"><h2>Chuỗi nội dung đề xuất</h2><div class="cards">{cards or '<p class="muted">Chưa đủ dữ liệu.</p>'}</div></section>
<section class="panel"><h2>Up Next ổn định qua replay</h2><table><thead><tr><th>Video</th><th>Appear</th><th>Mean pos</th></tr></thead><tbody>{stable_rows}</tbody></table></section>
<section class="panel note"><h2>Nguyên tắc giữ kênh tập trung</h2><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in profile["channel_focus_guardrails"])}</ul></section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_index")
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--html-output", required=True)
    parser.add_argument("--library-output", required=True)
    parser.add_argument("--history-output", default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    session_path = Path(args.session_index)
    if not session_path.is_absolute():
        session_path = repo_root / session_path
    session = read_json(session_path)
    profile = build_profile(repo_root, session)

    json_path = Path(args.json_output)
    html_path = Path(args.html_output)
    library_path = Path(args.library_output)
    for path in (json_path, html_path, library_path):
        if not path.is_absolute():
            path = repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)

    write_json(json_path, profile)
    html_path.write_text(render_html(profile), encoding="utf-8")
    write_json(library_path, profile)

    if args.history_output:
        history_path = Path(args.history_output)
        if not history_path.is_absolute():
            history_path = repo_root / history_path
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(profile, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(f"Consolidated profile JSON -> {json_path}")
    print(f"Consolidated profile HTML -> {html_path}")
    print(f"Profile library -> {library_path}")


if __name__ == "__main__":
    main()
