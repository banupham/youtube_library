#!/usr/bin/env python3
"""Context/entity multi-label classifier for YouTube Home snapshots.

Compared with v1:
- separates content category from content intent;
- uses entity/anchor/support evidence with different strengths;
- avoids ambiguous standalone AI token matching in Vietnamese;
- treats generic tutorial words as intent instead of forcing How-to & Style;
- supports optional YouTube API enrichment fields.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CONFIDENCE_WEIGHTS = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.2}


def normalize(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).casefold().strip()


def contains_phrase(text: str, phrase: str) -> bool:
    text = normalize(text)
    phrase = normalize(phrase)
    if not text or not phrase:
        return False
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text) is not None


def source_values(item: dict, source: str) -> list[str]:
    value = item.get(source)
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]


def should_suppress(category_id: str, phrase: str, text: str) -> bool:
    normalized = normalize(text)
    if category_id == "education" and normalize(phrase) == "lịch sử":
        if re.search(r"(?:hay|cháy|lớn|đỉnh|tệ|mạnh)\s+nhất\s+lịch\s+sử", normalized):
            return True
    return False


def score_categories(item: dict, rules: dict, *, target_mode: bool = False) -> tuple[dict[str, float], dict[str, list[dict]]]:
    scoring = rules["scoring"]
    kind_weights = {
        "entity": float(scoring["entity"]),
        "anchor": float(scoring["anchor"]),
        "support": float(scoring["support"]),
    }
    source_multipliers = dict(scoring["source_multipliers"])

    if target_mode:
        source_multipliers = {
            "title": 0.55,
            "channel": 0.15,
            "tags": 1.0,
            "description": 0.50,
            "youtube_topics": 0.45,
        }

    scores = {c["id"]: 0.0 for c in rules["categories"]}
    evidence = {c["id"]: [] for c in rules["categories"]}

    for category in rules["categories"]:
        cid = category["id"]
        for source, source_multiplier in source_multipliers.items():
            for text in source_values(item, source):
                for kind in ("entities", "anchors"):
                    evidence_kind = "entity" if kind == "entities" else "anchor"
                    for phrase in category.get(kind, []):
                        if should_suppress(cid, phrase, text):
                            continue
                        if contains_phrase(text, phrase):
                            added = kind_weights[evidence_kind] * source_multiplier
                            scores[cid] += added
                            evidence[cid].append({
                                "kind": evidence_kind,
                                "source": source,
                                "phrase": phrase,
                                "score": round(added, 3),
                            })

    for category in rules["categories"]:
        cid = category["id"]
        if scores[cid] <= 0:
            continue
        for source, source_multiplier in source_multipliers.items():
            for text in source_values(item, source):
                for phrase in category.get("support", []):
                    if contains_phrase(text, phrase):
                        added = kind_weights["support"] * source_multiplier
                        scores[cid] += added
                        evidence[cid].append({
                            "kind": "support",
                            "source": source,
                            "phrase": phrase,
                            "score": round(added, 3),
                        })

    youtube_category_id = item.get("youtube_category_id")
    if youtube_category_id is not None and not target_mode:
        try:
            youtube_category_id = int(youtube_category_id)
        except (TypeError, ValueError):
            pass
        for category in rules["categories"]:
            if youtube_category_id in category.get("youtube_video_category_ids", []):
                cid = category["id"]
                added = float(scoring["youtube_category"])
                scores[cid] += added
                evidence[cid].append({
                    "kind": "official_category",
                    "source": "youtube_category_id",
                    "phrase": str(youtube_category_id),
                    "score": round(added, 3),
                })

    return scores, evidence


def vector_from_scores(scores: dict[str, float], rules: dict) -> list[dict]:
    positive = {cid: value for cid, value in scores.items() if value > 0}
    if not positive:
        return []
    total = sum(positive.values())
    names = {c["id"]: c["name_vi"] for c in rules["categories"]}
    ranked = sorted(positive.items(), key=lambda x: x[1], reverse=True)
    top_share = ranked[0][1] / total
    threshold = max(0.08, top_share * 0.18)
    result = []
    for cid, raw in ranked:
        share = raw / total
        if share < threshold:
            continue
        result.append({
            "id": cid,
            "name_vi": names.get(cid, cid),
            "share": round(share, 4),
            "raw_score": round(raw, 3),
        })
    return result


def classify_content(item: dict, rules: dict) -> dict:
    scores, evidence = score_categories(item, rules)
    positive = {cid: score for cid, score in scores.items() if score > 0}
    enriched = any(item.get(k) for k in ("description", "tags", "youtube_category_id", "youtube_topics"))
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
    ranked = sorted(((cid, score / total) for cid, score in positive.items()), key=lambda x: x[1], reverse=True)
    top_id, top_share = ranked[0]
    second_share = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_share - second_share
    top_raw = scores[top_id]

    strong_evidence = [e for e in evidence[top_id] if e["kind"] in ("entity", "anchor", "official_category")]
    strong_sources = {e["source"] for e in strong_evidence}

    if top_raw >= 7.0 and len(strong_evidence) >= 2 and top_share >= 0.55 and margin >= 0.15:
        confidence = "high"
    elif top_raw >= 4.0 and len(strong_evidence) >= 1 and top_share >= 0.45:
        confidence = "medium"
    elif top_raw >= 2.0:
        confidence = "low"
    else:
        confidence = "unknown"

    if confidence == "medium" and len(strong_sources) >= 2 and top_share >= 0.55 and margin >= 0.20:
        confidence = "high"

    vector = vector_from_scores(scores, rules)
    selected_ids = {x["id"] for x in vector}
    return {
        "classification_mode": mode,
        "top_category": top_id,
        "confidence": confidence,
        "top_share": round(top_share, 4),
        "margin": round(margin, 4),
        "categories": vector,
        "evidence": {cid: evidence[cid] for cid, _ in ranked if cid in selected_ids and evidence[cid]},
    }


def classify_intent(item: dict, rules: dict) -> dict:
    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    tags = item.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]

    sources = [
        ("title", title, 1.0),
        ("description", description, 0.35),
        ("tags", " ".join(str(x) for x in tags), 0.65),
    ]
    scores: dict[str, float] = {}
    evidence: dict[str, list[dict]] = {}

    for intent_id, intent_rule in rules.get("intents", {}).items():
        score = 0.0
        found = []
        for source, text, multiplier in sources:
            if not text:
                continue
            for phrase in intent_rule.get("anchors", []):
                if contains_phrase(text, phrase):
                    added = 2.0 * multiplier
                    score += added
                    found.append({"source": source, "phrase": phrase, "score": round(added, 3)})
        if score > 0:
            scores[intent_id] = score
            evidence[intent_id] = found

    if not scores:
        return {"top_intent": None, "intents": [], "evidence": {}}

    total = sum(scores.values())
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for intent_id, score in ranked:
        share = score / total
        if share < 0.10:
            continue
        result.append({
            "id": intent_id,
            "name_vi": rules["intents"][intent_id].get("name_vi", intent_id),
            "share": round(share, 4),
        })
    selected = {x["id"] for x in result}
    return {
        "top_intent": result[0]["id"] if result else None,
        "intents": result,
        "evidence": {k: evidence[k] for k, _ in ranked if k in selected},
    }


def classify_target(item: dict, rules: dict) -> dict:
    if not item.get("tags") and not item.get("description"):
        return {
            "available": False,
            "reason": "Target profile needs creator-controlled metadata such as tags/description.",
            "categories": [],
        }
    scores, _ = score_categories(item, rules, target_mode=True)
    return {"available": True, "categories": vector_from_scores(scores, rules)}


def parse_published_at(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def popularity_profile(item: dict) -> dict:
    stats = item.get("statistics") or {}
    view_value = stats.get("view_count", item.get("view_count"))
    if view_value is None:
        return {"available": False}

    try:
        views = int(view_value)
    except (TypeError, ValueError):
        return {"available": False}

    result = {"available": True, "view_count": views}
    for key in ("like_count", "comment_count"):
        value = stats.get(key, item.get(key))
        if value is not None:
            try:
                result[key] = int(value)
            except (TypeError, ValueError):
                pass

    published = parse_published_at(item.get("published_at"))
    if published:
        age_hours = max(1.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600.0)
        result["age_days"] = round(age_hours / 24.0, 3)
        result["avg_views_per_day"] = round(views / (age_hours / 24.0), 2)
        result["demand_signal"] = round(min(1.0, math.log10(max(1.0, views / (age_hours / 24.0) + 1.0)) / 6.0), 4)
    return result


def summarize(results: list[dict]) -> dict:
    confidence = Counter(x["classification"]["confidence"] for x in results)
    top_categories = Counter(x["classification"]["top_category"] for x in results if x["classification"]["top_category"])
    n = len(results)
    known = n - confidence.get("unknown", 0)
    return {
        "video_count": n,
        "confidence_counts": dict(confidence),
        "classified_rate": round(known / n, 4) if n else 0.0,
        "high_medium_rate": round((confidence.get("high", 0) + confidence.get("medium", 0)) / n, 4) if n else 0.0,
        "ambiguous_or_unknown_rate": round((confidence.get("low", 0) + confidence.get("unknown", 0)) / n, 4) if n else 0.0,
        "top_category_distribution": dict(top_categories),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Homepage snapshot JSON")
    parser.add_argument("--rules", default="taxonomy/content_rules.v2.json", help="V2 rules JSON")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = repo_root / input_path
    rules_path = Path(args.rules)
    if not rules_path.is_absolute():
        rules_path = repo_root / rules_path

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    rules = json.loads(rules_path.read_text(encoding="utf-8"))

    results = []
    for item in payload.get("items", []):
        result_item = dict(item)
        result_item["classification"] = classify_content(item, rules)
        result_item["intent_profile"] = classify_intent(item, rules)
        result_item["target_profile"] = classify_target(item, rules)
        result_item["popularity_profile"] = popularity_profile(item)
        results.append(result_item)

    output = {
        "source": payload.get("source", "youtube_home"),
        "captured_at": payload.get("captured_at"),
        "classifier_version": rules.get("version"),
        "summary": summarize(results),
        "items": results,
    }

    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = repo_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
