#!/usr/bin/env python3
"""Build a longitudinal profile from one session profile plus daily evidence.

Phase 5.5 keeps three concepts separate:
- Home / Up Next = recommendation exposure.
- Subscriptions = explicit long-term affinity evidence.
- Daily history = longitudinal evidence used for decay and trend estimation.

All weights in this module are project heuristics for research. They are not
YouTube ranking probabilities or a reconstruction of YouTube's internal model.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import unicodedata
import urllib.parse
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

# Import creator-brief helpers from the session-level builder. This script is
# executed from the same directory, so the sibling module is importable.
from build_consolidated_profile import build_creative_blueprints  # type: ignore

SURFACE_PRIORS = {"home": 0.53, "up_next": 0.32, "subscriptions": 0.15}
CURRENT_WINDOW_WEIGHTS = {"today": 0.50, "7d": 0.30, "30d": 0.15, "long_term": 0.05}
WINDOW_CONFIG = {
    "7d": {"max_age_days": 6, "half_life_days": 3.5},
    "30d": {"max_age_days": 29, "half_life_days": 14.0},
    "long_term": {"max_age_days": None, "half_life_days": 60.0},
}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.2}
PRESENCE_THRESHOLD = 0.012

TREND_MOMENTUM = {
    "rising": 1.0,
    "emerging": 0.90,
    "revived": 0.85,
    "stable": 0.62,
    "cooling": 0.28,
    "dormant": 0.10,
    "baseline": 0.55,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", text).strip()


def pct(value: object) -> float:
    try:
        return float(value) * 100
    except (TypeError, ValueError):
        return 0.0


def normalize(values: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in values.values())
    if total <= 0:
        return {}
    return {k: max(0.0, float(v)) / total for k, v in values.items() if float(v) > 0}


def parse_day(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def position_weight(position: object) -> float:
    try:
        p = max(1, int(position))
    except (TypeError, ValueError):
        p = 1
    return 1.0 / math.log2(p + 1)


def item_categories(item: dict) -> list[dict]:
    content = (item.get("classification") or {}).get("categories") or []
    target = (item.get("target_profile") or {}).get("categories") or []
    combined: dict[str, dict] = {}
    for row in content:
        cid = row.get("id")
        if not cid:
            continue
        target_row = combined.setdefault(
            cid,
            {"id": cid, "name_vi": row.get("name_vi") or cid, "score": 0.0},
        )
        target_row["score"] += 0.85 * float(row.get("share") or 0.0)
    for row in target:
        cid = row.get("id")
        if not cid:
            continue
        target_row = combined.setdefault(
            cid,
            {"id": cid, "name_vi": row.get("name_vi") or cid, "score": 0.0},
        )
        target_row["score"] += 0.15 * float(row.get("share") or 0.0)
    total = sum(row["score"] for row in combined.values())
    if total <= 0:
        return []
    return [
        {"id": row["id"], "name_vi": row["name_vi"], "share": row["score"] / total}
        for row in combined.values()
    ]


def load_surface_payload(repo_root: Path, entry: dict) -> dict | None:
    value = entry.get("classified_path") or entry.get("snapshot_path")
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        return None
    return read_json(path)


def subscription_evidence(repo_root: Path, session: dict) -> dict:
    entries = ((session.get("surfaces") or {}).get("subscriptions") or [])
    if not entries:
        return {
            "category_distribution": {},
            "category_names": {},
            "item_count": 0,
            "channels": [],
            "keywords": {},
            "tags": {},
        }

    entry = entries[-1]
    payload = load_surface_payload(repo_root, entry) or {}
    items = payload.get("items") or []
    scores: dict[str, float] = defaultdict(float)
    names: dict[str, str] = {}
    keyword_scores: dict[str, dict] = {}
    tag_scores: dict[str, dict] = {}

    def add_term(bucket: dict[str, dict], value: object, score: float) -> None:
        display = str(value or "").strip().lstrip("#")
        key = norm(display)
        if len(key) < 2 or score <= 0:
            return
        row = bucket.setdefault(key, {"value": display, "score": 0.0})
        row["score"] += score

    for idx, item in enumerate(items, start=1):
        confidence = str((item.get("classification") or {}).get("confidence") or "unknown")
        base = position_weight(item.get("position") or idx) * CONFIDENCE_WEIGHT.get(confidence, 0.2)
        categories = item_categories(item)
        for category in categories:
            cid = str(category["id"])
            contribution = base * float(category.get("share") or 0.0)
            scores[cid] += contribution
            names[cid] = str(category.get("name_vi") or cid)

            evidence = ((item.get("classification") or {}).get("evidence") or {}).get(cid) or []
            for ev in evidence:
                phrase = str(ev.get("phrase") or "").strip()
                if phrase and not phrase.isdigit():
                    add_term(keyword_scores, phrase, contribution)

        title = norm(item.get("title"))
        description = norm(item.get("description"))
        content_text = f"{title} {description}".strip()
        for tag in item.get("tags") or []:
            display = str(tag or "").strip()
            key = norm(display)
            if not key:
                continue
            tokens = [x for x in re.findall(r"\w+", key, flags=re.UNICODE) if len(x) >= 3]
            if key in content_text:
                consistency = 1.0
            elif tokens:
                overlap = sum(1 for token in tokens if token in content_text) / len(tokens)
                consistency = 0.85 if overlap >= 0.75 else 0.60 if overlap >= 0.40 else 0.35
            else:
                consistency = 0.35
            add_term(tag_scores, display, base * consistency)
            add_term(keyword_scores, display, base * consistency * 0.70)

        for topic in item.get("youtube_topics") or []:
            label = urllib.parse.unquote(str(topic).rsplit("/", 1)[-1]).replace("_", " ").strip()
            if label:
                add_term(keyword_scores, label, base * 0.90)

    channels = []
    seen_channels = set()
    for row in payload.get("subscription_channels") or []:
        channel_id = str(row.get("channel_id") or "").strip()
        name = str(row.get("name") or "").strip()
        key = channel_id or norm(name)
        if not key or key in seen_channels:
            continue
        seen_channels.add(key)
        channels.append(
            {
                "channel_id": channel_id or None,
                "name": name or channel_id or "Unknown channel",
                "url": row.get("url"),
                "subscriber_text": row.get("subscriber_text"),
                "video_count_text": row.get("video_count_text"),
            }
        )

    return {
        "category_distribution": normalize(scores),
        "category_names": names,
        "item_count": len(items),
        "channels": channels,
        "keywords": keyword_scores,
        "tags": tag_scores,
    }


def reconstruct_surface_distributions(session_profile: dict) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    home: dict[str, float] = {}
    up_next: dict[str, float] = {}
    names: dict[str, str] = {}
    for row in session_profile.get("interest_weights") or []:
        cid = str(row.get("id") or "")
        if not cid:
            continue
        names[cid] = str(row.get("name_vi") or cid)
        home[cid] = float(row.get("home_weight") or 0.0)
        up_next[cid] = float(row.get("up_next_weight") or 0.0)
    return normalize(home), normalize(up_next), names


def combine_surfaces(surface_dists: dict[str, dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    available = [name for name, dist in surface_dists.items() if dist]
    if not available:
        return {}, {}
    denominator = sum(SURFACE_PRIORS[name] for name in available)
    applied = {name: SURFACE_PRIORS[name] / denominator for name in available}
    combined: dict[str, float] = defaultdict(float)
    for surface, dist in surface_dists.items():
        if surface not in applied:
            continue
        for cid, value in dist.items():
            combined[cid] += applied[surface] * value
    return normalize(combined), applied


def normalized_term_map(rows: list[dict], extra: dict[str, dict] | None = None, extra_weight: float = 0.15) -> dict[str, dict]:
    raw: dict[str, dict] = {}
    for row in rows:
        value = str(row.get("value") or "").strip()
        key = norm(value)
        score = float(row.get("score") or 0.0)
        if not key or score <= 0:
            continue
        target = raw.setdefault(key, {"value": value, "score": 0.0})
        target["score"] += score

    base_total = sum(x["score"] for x in raw.values())
    if base_total > 0:
        for row in raw.values():
            row["score"] = (1.0 - extra_weight) * row["score"] / base_total

    if extra:
        extra_total = sum(float(x.get("score") or 0.0) for x in extra.values())
        if extra_total > 0:
            for key, row in extra.items():
                score = extra_weight * float(row.get("score") or 0.0) / extra_total
                target = raw.setdefault(key, {"value": row.get("value") or key, "score": 0.0})
                target["score"] += score

    total = sum(x["score"] for x in raw.values())
    if total > 0:
        for row in raw.values():
            row["score"] /= total
    return raw


def make_daily_observation(
    session_profile: dict,
    session: dict,
    repo_root: Path,
    observation_day: date,
) -> dict:
    home_dist, up_dist, names = reconstruct_surface_distributions(session_profile)
    subscriptions = subscription_evidence(repo_root, session)
    for cid, name in subscriptions["category_names"].items():
        names.setdefault(cid, name)

    surface_dists = {
        "home": home_dist,
        "up_next": up_dist,
        "subscriptions": subscriptions["category_distribution"],
    }
    combined, applied = combine_surfaces(surface_dists)

    keyword_map = normalized_term_map(
        session_profile.get("creative_keywords") or [],
        subscriptions.get("keywords") or {},
    )
    tag_map = normalized_term_map(
        session_profile.get("creative_tags") or [],
        subscriptions.get("tags") or {},
    )

    interest_rows = {
        cid: {
            "name_vi": names.get(cid, cid),
            "weight": round(weight, 6),
            "surfaces": {
                surface: round(dist.get(cid, 0.0), 6)
                for surface, dist in surface_dists.items()
                if dist.get(cid, 0.0) > 0
            },
        }
        for cid, weight in combined.items()
    }

    now = datetime.now().astimezone()
    return {
        "version": "1.0.0",
        "date": observation_day.isoformat(),
        "recorded_at": now.isoformat(),
        "timezone": str(now.tzinfo),
        "collection_session_id": session_profile.get("collection_session_id"),
        "candidate_profile_name": session_profile.get("behavior_profile_name"),
        "surface_weights_applied": {k: round(v, 6) for k, v in applied.items()},
        "surface_evidence": {
            **(session_profile.get("surface_evidence") or {}),
            "subscription_items": subscriptions["item_count"],
            "subscription_channels_observed": len(subscriptions["channels"]),
        },
        "interest_weights": interest_rows,
        "keyword_weights": {
            key: {"value": row["value"], "weight": round(row["score"], 6)}
            for key, row in keyword_map.items()
        },
        "tag_weights": {
            key: {"value": row["value"], "weight": round(row["score"], 6)}
            for key, row in tag_map.items()
        },
        "subscription_channels": subscriptions["channels"],
        "same_day_policy": "latest_collection_replaces_previous_daily_observation",
    }


def load_daily_observations(daily_dir: Path) -> list[dict]:
    rows = []
    if not daily_dir.exists():
        return rows
    for path in sorted(daily_dir.glob("*.json")):
        try:
            row = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if parse_day(row.get("date")):
            rows.append(row)
    rows.sort(key=lambda row: str(row.get("date") or ""))
    return rows


def vector_from_observation(obs: dict, field: str) -> dict[str, float]:
    if field == "interest_weights":
        return {
            key: float(row.get("weight") or 0.0)
            for key, row in (obs.get(field) or {}).items()
            if float(row.get("weight") or 0.0) > 0
        }
    return {
        key: float(row.get("weight") or 0.0)
        for key, row in (obs.get(field) or {}).items()
        if float(row.get("weight") or 0.0) > 0
    }


def rolling_vector(
    observations: list[dict],
    field: str,
    today: date,
    *,
    max_age_days: int | None,
    half_life_days: float,
    exclude_today: bool = False,
) -> dict[str, float]:
    total_day_weight = 0.0
    scores: dict[str, float] = defaultdict(float)
    for obs in observations:
        obs_day = parse_day(obs.get("date"))
        if not obs_day:
            continue
        age = (today - obs_day).days
        if age < 0:
            continue
        if exclude_today and age == 0:
            continue
        if max_age_days is not None and age > max_age_days:
            continue
        day_weight = 0.5 ** (age / max(0.1, half_life_days))
        vector = vector_from_observation(obs, field)
        if not vector:
            continue
        total_day_weight += day_weight
        for key, value in vector.items():
            scores[key] += day_weight * value
    if total_day_weight <= 0:
        return {}
    return normalize({key: value / total_day_weight for key, value in scores.items()})


def trend_state(
    cid: str,
    today_weight: float,
    previous_7d: float,
    rolling_30d: float,
    observations: list[dict],
    today: date,
) -> tuple[str, float, dict]:
    previous_days = []
    present_days = []
    for obs in observations:
        obs_day = parse_day(obs.get("date"))
        if not obs_day:
            continue
        value = float(((obs.get("interest_weights") or {}).get(cid) or {}).get("weight") or 0.0)
        if value >= PRESENCE_THRESHOLD:
            present_days.append(obs_day)
            if obs_day < today:
                previous_days.append(obs_day)

    history_before_today = len({parse_day(x.get("date")) for x in observations if parse_day(x.get("date")) and parse_day(x.get("date")) < today})
    first_seen = min(present_days).isoformat() if present_days else None
    last_seen = max(present_days).isoformat() if present_days else None
    days_present = len(set(present_days))

    if history_before_today == 0:
        state = "baseline"
    elif today_weight < 0.005 and rolling_30d >= 0.02:
        state = "dormant"
    else:
        previous_last = max(previous_days) if previous_days else None
        gap = (today - previous_last).days if previous_last else None
        if today_weight >= 0.02 and previous_last and gap is not None and gap >= 7:
            state = "revived"
        elif today_weight >= 0.03 and days_present <= 2 and first_seen and (today - date.fromisoformat(first_seen)).days <= 2:
            state = "emerging"
        elif previous_7d > 0 and today_weight >= previous_7d + 0.02 and today_weight >= previous_7d * 1.18:
            state = "rising"
        elif previous_7d >= 0.02 and today_weight + 0.02 <= previous_7d and today_weight <= previous_7d * 0.82:
            state = "cooling"
        else:
            state = "stable"

    confidence = min(1.0, 0.20 + 0.12 * min(6, history_before_today) + 0.08 * min(4, days_present))
    return state, confidence, {
        "first_seen": first_seen,
        "last_seen": last_seen,
        "days_present": days_present,
        "previous_7d_weight": round(previous_7d, 4),
    }


def temporal_interest_rows(
    session_profile: dict,
    observations: list[dict],
    previous_profile: dict | None,
    today: date,
) -> tuple[list[dict], dict]:
    today_vec = rolling_vector(observations, "interest_weights", today, max_age_days=0, half_life_days=1.0)
    vec7 = rolling_vector(observations, "interest_weights", today, **WINDOW_CONFIG["7d"])
    vec30 = rolling_vector(observations, "interest_weights", today, **WINDOW_CONFIG["30d"])
    veclong = rolling_vector(observations, "interest_weights", today, **WINDOW_CONFIG["long_term"])
    prev7 = rolling_vector(
        observations,
        "interest_weights",
        today,
        max_age_days=7,
        half_life_days=3.5,
        exclude_today=True,
    )

    current_meta = {str(row.get("id")): row for row in session_profile.get("interest_weights") or [] if row.get("id")}
    previous_meta = {
        str(row.get("id")): row
        for row in ((previous_profile or {}).get("interest_weights") or [])
        if row.get("id")
    }

    composite: dict[str, float] = defaultdict(float)
    all_ids = set(today_vec) | set(vec7) | set(vec30) | set(veclong)
    for cid in all_ids:
        composite[cid] = (
            CURRENT_WINDOW_WEIGHTS["today"] * today_vec.get(cid, 0.0)
            + CURRENT_WINDOW_WEIGHTS["7d"] * vec7.get(cid, 0.0)
            + CURRENT_WINDOW_WEIGHTS["30d"] * vec30.get(cid, 0.0)
            + CURRENT_WINDOW_WEIGHTS["long_term"] * veclong.get(cid, 0.0)
        )
    composite = normalize(composite)
    ordered = sorted(composite.items(), key=lambda pair: pair[1], reverse=True)
    top_share = ordered[0][1] if ordered else 0.0

    today_obs = next((x for x in reversed(observations) if str(x.get("date")) == today.isoformat()), {})
    today_interest = today_obs.get("interest_weights") or {}
    rows = []
    for idx, (cid, weight) in enumerate(ordered):
        meta = current_meta.get(cid) or previous_meta.get(cid) or {}
        name_vi = str(meta.get("name_vi") or ((today_interest.get(cid) or {}).get("name_vi")) or cid)
        state, trend_confidence, persistence = trend_state(
            cid,
            today_vec.get(cid, 0.0),
            prev7.get(cid, 0.0),
            vec30.get(cid, 0.0),
            observations,
            today,
        )

        if idx == 0 or weight >= max(0.18, top_share * 0.55):
            zone = "core"
        elif weight >= max(0.065, top_share * 0.22):
            zone = "adjacent"
        else:
            zone = "exploration"

        surface_values = (today_interest.get(cid) or {}).get("surfaces") or {}
        cross_surface = sum(1 for value in surface_values.values() if float(value or 0.0) > 0) >= 2
        demand = float(meta.get("demand_signal") or 0.25)
        stability = min(1.0, float(surface_values.get("up_next") or 0.0) / max(0.001, today_vec.get(cid, weight)))
        relative_fit = weight / max(0.001, top_share)
        momentum = TREND_MOMENTUM.get(state, 0.55)
        opportunity = (
            0.48 * relative_fit
            + 0.18 * demand
            + 0.10 * stability
            + 0.08 * (1.0 if cross_surface else 0.35)
            + 0.16 * momentum
        )

        rows.append(
            {
                "id": cid,
                "name_vi": name_vi,
                "predicted_weight": round(weight, 4),
                "today_weight": round(today_vec.get(cid, 0.0), 4),
                "weight_7d": round(vec7.get(cid, 0.0), 4),
                "weight_30d": round(vec30.get(cid, 0.0), 4),
                "long_term_weight": round(veclong.get(cid, 0.0), 4),
                "trend_state": state,
                "trend_confidence": round(trend_confidence, 4),
                "zone": zone,
                "home_weight": round(float(surface_values.get("home") or 0.0), 4),
                "up_next_weight": round(float(surface_values.get("up_next") or 0.0), 4),
                "subscription_weight": round(float(surface_values.get("subscriptions") or 0.0), 4),
                "cross_surface": cross_surface,
                "demand_signal": round(demand, 4),
                "opportunity_score": round(max(0.0, min(1.0, opportunity)), 4),
                "keywords": meta.get("keywords") or [],
                "creative_tags": meta.get("creative_tags") or [],
                "persistence": persistence,
            }
        )

    windows = {
        "today": {k: round(v, 6) for k, v in today_vec.items()},
        "7d": {k: round(v, 6) for k, v in vec7.items()},
        "30d": {k: round(v, 6) for k, v in vec30.items()},
        "long_term": {k: round(v, 6) for k, v in veclong.items()},
        "current_mix": {k: round(v, 6) for k, v in composite.items()},
    }
    return rows, windows


def term_trends(observations: list[dict], field: str, today: date, limit: int) -> list[dict]:
    today_vec = rolling_vector(observations, field, today, max_age_days=0, half_life_days=1.0)
    vec7 = rolling_vector(observations, field, today, **WINDOW_CONFIG["7d"])
    vec30 = rolling_vector(observations, field, today, **WINDOW_CONFIG["30d"])
    veclong = rolling_vector(observations, field, today, **WINDOW_CONFIG["long_term"])
    prev7 = rolling_vector(observations, field, today, max_age_days=7, half_life_days=3.5, exclude_today=True)

    display: dict[str, str] = {}
    for obs in observations:
        for key, row in (obs.get(field) or {}).items():
            display[key] = str(row.get("value") or key)

    keys = set(today_vec) | set(vec7) | set(vec30) | set(veclong)
    rows = []
    for key in keys:
        today_value = today_vec.get(key, 0.0)
        previous = prev7.get(key, 0.0)
        if len(observations) <= 1:
            state = "baseline"
        elif today_value >= 0.01 and previous == 0:
            state = "emerging"
        elif previous > 0 and today_value >= previous * 1.25 and today_value >= previous + 0.005:
            state = "rising"
        elif previous >= 0.005 and today_value <= previous * 0.75:
            state = "cooling"
        else:
            state = "stable"
        current = (
            CURRENT_WINDOW_WEIGHTS["today"] * today_value
            + CURRENT_WINDOW_WEIGHTS["7d"] * vec7.get(key, 0.0)
            + CURRENT_WINDOW_WEIGHTS["30d"] * vec30.get(key, 0.0)
            + CURRENT_WINDOW_WEIGHTS["long_term"] * veclong.get(key, 0.0)
        )
        rows.append(
            {
                "value": display.get(key, key),
                "weight": round(current, 4),
                "today_weight": round(today_value, 4),
                "weight_7d": round(vec7.get(key, 0.0), 4),
                "weight_30d": round(vec30.get(key, 0.0), 4),
                "long_term_weight": round(veclong.get(key, 0.0), 4),
                "trend_state": state,
            }
        )
    rows.sort(key=lambda row: row["weight"], reverse=True)
    return rows[:limit]


def subscription_channel_history(observations: list[dict], today: date, limit: int = 60) -> list[dict]:
    stats: dict[str, dict] = {}
    for obs in observations:
        obs_day = parse_day(obs.get("date"))
        if not obs_day:
            continue
        for channel in obs.get("subscription_channels") or []:
            channel_id = str(channel.get("channel_id") or "").strip()
            name = str(channel.get("name") or "").strip()
            key = channel_id or norm(name)
            if not key:
                continue
            row = stats.setdefault(
                key,
                {
                    "channel_id": channel_id or None,
                    "name": name or channel_id or "Unknown channel",
                    "url": channel.get("url"),
                    "days": set(),
                    "first_seen": obs_day,
                    "last_seen": obs_day,
                },
            )
            row["days"].add(obs_day)
            row["first_seen"] = min(row["first_seen"], obs_day)
            row["last_seen"] = max(row["last_seen"], obs_day)
            if channel.get("url"):
                row["url"] = channel.get("url")

    current_obs = next((x for x in reversed(observations) if str(x.get("date")) == today.isoformat()), {})
    current_keys = {
        str(x.get("channel_id") or "").strip() or norm(x.get("name"))
        for x in current_obs.get("subscription_channels") or []
    }
    output = []
    for key, row in stats.items():
        output.append(
            {
                "channel_id": row["channel_id"],
                "name": row["name"],
                "url": row["url"],
                "observed_today": key in current_keys,
                "observed_days": len(row["days"]),
                "first_seen": row["first_seen"].isoformat(),
                "last_seen": row["last_seen"].isoformat(),
                "note": "Absence is not treated as unsubscribe because the read-only channel page may be incomplete.",
            }
        )
    output.sort(key=lambda row: (row["observed_today"], row["observed_days"], row["name"]), reverse=True)
    return output[:limit]


def stable_profile_name(candidate: str, observations: list[dict], previous_profile: dict | None) -> dict:
    previous_name = str((previous_profile or {}).get("behavior_profile_name") or "").strip()
    consecutive = 0
    for obs in reversed(observations):
        if str(obs.get("candidate_profile_name") or "") == candidate:
            consecutive += 1
        else:
            break

    if not previous_name:
        stable = candidate
        status = "initialized"
    elif previous_name == candidate:
        stable = previous_name
        status = "stable"
    elif consecutive >= 3:
        stable = candidate
        status = "promoted_after_3_daily_observations"
    else:
        stable = previous_name
        status = "candidate_waiting_for_stability"

    previous_names = list(((previous_profile or {}).get("profile_name_state") or {}).get("previous_names") or [])
    if previous_name and stable != previous_name and previous_name not in previous_names:
        previous_names.append(previous_name)

    return {
        "stable_name": stable,
        "candidate_name": candidate,
        "candidate_consecutive_days": consecutive,
        "status": status,
        "promotion_rule": "candidate must persist for 3 consecutive daily observations before replacing an existing stable name",
        "previous_names": previous_names[-10:],
    }


def build_phases(interests: list[dict]) -> list[dict]:
    active = [row for row in interests if row.get("trend_state") != "dormant"]
    if not active:
        active = interests
    phases = []
    if active:
        anchor = active[0]
        phases.append(
            {
                "phase": 1,
                "role": "anchor",
                "direction": anchor["name_vi"],
                "recommended_share_of_next_videos": "60-70%",
                "goal": "Giữ content DNA quanh interest mạnh và bền nhất; ưu tiên stable/rising trước tín hiệu nhất thời.",
                "keywords": [x.get("value") for x in anchor.get("keywords") or [] if x.get("value")][:8],
                "tags": [x.get("value") for x in anchor.get("creative_tags") or [] if x.get("value")][:8],
                "trend_state": anchor.get("trend_state"),
            }
        )
    if len(active) > 1:
        bridge = next(
            (
                row
                for row in active[1:]
                if row.get("cross_surface") and row.get("trend_state") in {"rising", "stable", "emerging", "revived", "baseline"}
            ),
            active[1],
        )
        phases.append(
            {
                "phase": 2,
                "role": "bridge",
                "direction": bridge["name_vi"],
                "recommended_share_of_next_videos": "20-30%",
                "goal": "Mở rộng sang lane kế cận có cross-surface hoặc xu hướng tăng, nhưng vẫn giữ keyword/chủ đề chung với anchor.",
                "keywords": [x.get("value") for x in bridge.get("keywords") or [] if x.get("value")][:8],
                "tags": [x.get("value") for x in bridge.get("creative_tags") or [] if x.get("value")][:8],
                "trend_state": bridge.get("trend_state"),
            }
        )
    if len(active) > 2:
        explore = next(
            (
                row
                for row in active[2:]
                if row.get("trend_state") in {"emerging", "rising", "revived"}
            ),
            active[2],
        )
        phases.append(
            {
                "phase": 3,
                "role": "controlled_expansion",
                "direction": explore["name_vi"],
                "recommended_share_of_next_videos": "<=10-15%",
                "goal": "Chỉ thử một lane mới khi tín hiệu đang nổi lên hoặc hồi sinh; không pivot cả kênh từ một snapshot.",
                "keywords": [x.get("value") for x in explore.get("keywords") or [] if x.get("value")][:8],
                "tags": [x.get("value") for x in explore.get("creative_tags") or [] if x.get("value")][:8],
                "trend_state": explore.get("trend_state"),
            }
        )
    return phases


def build_temporal_profile(
    repo_root: Path,
    session_profile: dict,
    session: dict,
    daily_dir: Path,
    previous_profile: dict | None,
) -> dict:
    today = datetime.now().astimezone().date()
    daily_dir.mkdir(parents=True, exist_ok=True)
    daily_observation = make_daily_observation(session_profile, session, repo_root, today)
    write_json(daily_dir / f"{today.isoformat()}.json", daily_observation)
    observations = load_daily_observations(daily_dir)

    interests, windows = temporal_interest_rows(session_profile, observations, previous_profile, today)
    keyword_trends = term_trends(observations, "keyword_weights", today, 40)
    tag_trends = term_trends(observations, "tag_weights", today, 35)
    channels = subscription_channel_history(observations, today)

    top_share = float(interests[0].get("predicted_weight") or 0.0) if interests else 0.0
    probs = [float(row.get("predicted_weight") or 0.0) for row in interests if float(row.get("predicted_weight") or 0.0) > 0]
    diversity = 0.0
    if len(probs) > 1:
        diversity = -sum(p * math.log(p) for p in probs) / math.log(len(probs))

    intent_rows = session_profile.get("intent_weights") or []
    intent_map = {str(row.get("id")): float(row.get("weight") or 0.0) for row in intent_rows if row.get("id")}
    top_intent_label = str(intent_rows[0].get("label") or "Explorer") if intent_rows else "Explorer"
    top_category = interests[0]["name_vi"] if interests else "Insufficient signal"
    candidate_name = (
        f"{top_category} · {top_intent_label}"
        if top_share >= 0.34
        else f"Multi-interest · {top_intent_label}"
        if diversity >= 0.72
        else f"{top_category}-leaning · {top_intent_label}"
    )
    name_state = stable_profile_name(candidate_name, observations, previous_profile)

    phases = build_phases(interests)
    blueprints = build_creative_blueprints(interests, phases, intent_map)

    distinct_days = len({str(obs.get("date")) for obs in observations if obs.get("date")})
    subscription_today = daily_observation.get("surface_evidence") or {}
    base_certainty = float(session_profile.get("certainty_score") or 0.0)
    history_bonus = 0.08 * min(1.0, max(0, distinct_days - 1) / 7.0)
    subscription_bonus = 0.04 if int(subscription_today.get("subscription_channels_observed") or 0) > 0 else 0.0
    certainty = min(0.86, base_certainty + history_bonus + subscription_bonus)

    output = dict(session_profile)
    output.update(
        {
            "analysis_version": "2.5.0",
            "model_stage": "longitudinal_home_up_next_subscriptions_prior",
            "behavior_profile_name": name_state["stable_name"],
            "profile_name_state": name_state,
            "session_interest_weights": session_profile.get("interest_weights") or [],
            "interest_weights": interests,
            "diversity_score": round(diversity, 4),
            "certainty_score": round(certainty, 4),
            "uncertainty_score": round(1.0 - certainty, 4),
            "content_series_plan": phases,
            "creative_blueprints": blueprints,
            "keyword_trends": keyword_trends,
            "tag_trends": tag_trends,
            "subscription_channel_affinity": channels,
            "temporal_profile": {
                "phase": "5.5",
                "observation_date": today.isoformat(),
                "daily_observation_count": distinct_days,
                "daily_snapshot_policy": "latest collection replaces the same calendar day's observation",
                "surface_priors": SURFACE_PRIORS,
                "current_window_weights": CURRENT_WINDOW_WEIGHTS,
                "window_config": WINDOW_CONFIG,
                "interest_windows": windows,
                "trend_states": ["baseline", "emerging", "rising", "stable", "cooling", "dormant", "revived"],
                "note": "Temporal decay and trend states are project heuristics, not YouTube internal signals.",
            },
            "updated_at": datetime.now().astimezone().isoformat(),
        }
    )
    evidence = dict(output.get("surface_evidence") or {})
    evidence.update(
        {
            "subscription_items": int(subscription_today.get("subscription_items") or 0),
            "subscription_channels_observed": int(subscription_today.get("subscription_channels_observed") or 0),
            "daily_observation_count": distinct_days,
        }
    )
    output["surface_evidence"] = evidence
    basis = dict(output.get("behavior_profile_name_basis") or {})
    basis.update(
        {
            "candidate_name": candidate_name,
            "stable_name": name_state["stable_name"],
            "name_stability_rule": name_state["promotion_rule"],
        }
    )
    output["behavior_profile_name_basis"] = basis
    output.setdefault("channel_focus_guardrails", []).extend(
        [
            "Không pivot theo một ngày đơn lẻ; ưu tiên interest stable/rising qua nhiều daily observations.",
            "Subscriptions là explicit-affinity evidence và decay chậm hơn recommendation exposure, nhưng không được coi là lịch sử xem.",
            "Không suy luận unsubscribe chỉ vì một channel vắng mặt trong snapshot read-only; trang channel list có thể không đầy đủ.",
        ]
    )
    interpretation = dict(output.get("interpretation") or {})
    interpretation.update(
        {
            "temporal_profile": "Current profile mixes today/7d/30d/long-term observations with exponential decay; all parameters are research heuristics.",
            "subscriptions": "Subscribed-channel and subscription-feed observations are explicit affinity evidence, not proof of watch behavior.",
            "trend_state": "Rising/cooling/emerging/etc. describe change in observed exposure/affinity evidence across daily snapshots, not YouTube's own labels.",
        }
    )
    output["interpretation"] = interpretation
    return output


def render_html(profile: dict) -> str:
    identity = profile.get("profile") or {}
    evidence = profile.get("surface_evidence") or {}
    temporal = profile.get("temporal_profile") or {}
    interests = profile.get("interest_weights") or []
    phases = profile.get("content_series_plan") or []
    blueprints = profile.get("creative_blueprints") or []
    keyword_trends = profile.get("keyword_trends") or []
    tag_trends = profile.get("tag_trends") or []
    channels = profile.get("subscription_channel_affinity") or []
    stable = profile.get("stable_up_next") or []

    bars = "".join(
        '<div class="interest">'
        f'<div class="interest-head"><b>{html.escape(str(row.get("name_vi") or row.get("id") or ""))}</b>'
        f'<span class="trend {html.escape(str(row.get("trend_state") or "stable"))}">{html.escape(str(row.get("trend_state") or "stable"))}</span>'
        f'<strong>{pct(row.get("predicted_weight")):.1f}%</strong></div>'
        f'<div class="track"><i style="width:{max(1.0,pct(row.get("predicted_weight"))):.2f}%"></i></div>'
        f'<small>Today {pct(row.get("today_weight")):.1f}% · 7d {pct(row.get("weight_7d")):.1f}% · '
        f'30d {pct(row.get("weight_30d")):.1f}% · Long {pct(row.get("long_term_weight")):.1f}%</small><br>'
        f'<small>Home {pct(row.get("home_weight")):.1f}% · Up Next {pct(row.get("up_next_weight")):.1f}% · '
        f'Subscriptions {pct(row.get("subscription_weight")):.1f}% · Opportunity {float(row.get("opportunity_score") or 0):.2f}</small>'
        '</div>'
        for row in interests[:14]
    )

    phase_cards = "".join(
        '<article>'
        f'<small>Phase {row.get("phase")} · {html.escape(str(row.get("role") or ""))} · '
        f'{html.escape(str(row.get("recommended_share_of_next_videos") or ""))}</small>'
        f'<h3>{html.escape(str(row.get("direction") or ""))}</h3>'
        f'<p>{html.escape(str(row.get("goal") or ""))}</p>'
        f'<p><b>Trend:</b> {html.escape(str(row.get("trend_state") or "—"))}</p>'
        f'<p><b>Keywords:</b> {html.escape(", ".join(str(x) for x in row.get("keywords") or []) or "—")}</p>'
        f'<p><b>Tags:</b> {html.escape(", ".join(str(x) for x in row.get("tags") or []) or "—")}</p>'
        '</article>'
        for row in phases
    )

    blueprint_cards = []
    for b in blueprints:
        tg = b.get("title_guidance") or {}
        dg = b.get("description_guidance") or {}
        tagg = b.get("tag_guidance") or {}
        cb = b.get("content_blueprint") or {}
        titles = "".join(f"<li>{html.escape(str(x))}</li>" for x in tg.get("suggested_titles") or [])
        sections = "".join(
            f'<li><b>{html.escape(str(x.get("role") or ""))}</b>: {html.escape(str(x.get("guidance") or ""))}</li>'
            for x in cb.get("sections") or []
        )
        blueprint_cards.append(
            '<article class="blueprint">'
            f'<small>{html.escape(str(b.get("lane") or ""))} · Profile fit {pct(b.get("profile_fit")):.1f}% · '
            f'Opportunity {float(b.get("opportunity_score") or 0):.2f}</small>'
            f'<h3>{html.escape(str(b.get("direction") or ""))}</h3>'
            f'<p><b>Format:</b> {html.escape(str(cb.get("recommended_format") or "—"))}</p>'
            f'<p><b>Tiêu đề nên chứa:</b> {html.escape(", ".join(str(x) for x in tg.get("should_include_any") or []) or "—")}</p>'
            f'<ul>{titles}</ul>'
            f'<p><b>Mô tả nên chứa:</b> {html.escape(", ".join(str(x) for x in dg.get("should_include_terms") or []) or "—")}</p>'
            f'<p><b>Observed tags:</b> {html.escape(", ".join(str(x) for x in tagg.get("observed_consistent_tags") or []) or "—")}</p>'
            f'<p><b>Hook:</b> {html.escape(str(cb.get("hook_guidance") or "—"))}</p>'
            f'<ol>{sections}</ol>'
            '</article>'
        )

    keyword_rows = "".join(
        f'<tr><td>{html.escape(str(row.get("value") or ""))}</td><td>{html.escape(str(row.get("trend_state") or ""))}</td>'
        f'<td>{pct(row.get("today_weight")):.1f}%</td><td>{pct(row.get("weight_7d")):.1f}%</td><td>{pct(row.get("weight_30d")):.1f}%</td></tr>'
        for row in keyword_trends[:25]
    )
    tag_rows = "".join(
        f'<tr><td>{html.escape(str(row.get("value") or ""))}</td><td>{html.escape(str(row.get("trend_state") or ""))}</td>'
        f'<td>{pct(row.get("today_weight")):.1f}%</td><td>{pct(row.get("weight_7d")):.1f}%</td><td>{pct(row.get("weight_30d")):.1f}%</td></tr>'
        for row in tag_trends[:25]
    )
    channel_rows = "".join(
        f'<tr><td>{html.escape(str(row.get("name") or ""))}</td><td>{"yes" if row.get("observed_today") else "history"}</td>'
        f'<td>{int(row.get("observed_days") or 0)}</td><td>{html.escape(str(row.get("first_seen") or ""))}</td>'
        f'<td>{html.escape(str(row.get("last_seen") or ""))}</td></tr>'
        for row in channels[:40]
    )
    stable_rows = "".join(
        f'<tr><td>{html.escape(str(row.get("title") or ""))}</td><td>{row.get("appearances")}/{row.get("replay_count")}</td>'
        f'<td>{float(row.get("mean_position") or 0):.1f}</td></tr>'
        for row in stable[:20]
    )

    name_state = profile.get("profile_name_state") or {}
    candidate_note = ""
    if name_state.get("candidate_name") and name_state.get("candidate_name") != name_state.get("stable_name"):
        candidate_note = (
            f'<p class="muted">Candidate name: <b>{html.escape(str(name_state.get("candidate_name")))}</b> · '
            f'{int(name_state.get("candidate_consecutive_days") or 0)}/3 ngày liên tiếp trước khi đổi tên ổn định.</p>'
        )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube Longitudinal Profile</title>
<style>
body{{margin:0;background:#0f1115;color:#f4f6f8;font-family:Inter,system-ui,sans-serif}}main{{max-width:1220px;margin:auto;padding:28px 18px 60px}}
.hero,.panel,article{{background:#171a20;border:1px solid #30343d;border-radius:18px}}.hero,.panel{{padding:20px;margin-bottom:16px}}h1,h2,h3{{margin:.2em 0 .6em}}
.muted,small{{color:#aab1bd}}.stats,.grid,.cards{{display:grid;gap:12px}}.stats{{grid-template-columns:repeat(auto-fit,minmax(145px,1fr))}}.grid{{grid-template-columns:1fr 1fr}}
.cards{{grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}}.stat,article{{background:#20242c;padding:14px;border-radius:14px}}.stat strong{{display:block;font-size:1.35rem;margin-top:4px}}
.interest{{margin:14px 0}}.interest-head{{display:flex;gap:9px;align-items:center}}.interest-head strong{{margin-left:auto}}.track{{height:10px;background:#2b3039;border-radius:999px;overflow:hidden;margin:5px 0}}.track i{{display:block;height:100%;background:#9aacff}}
.trend{{font-size:.72rem;padding:3px 7px;border-radius:999px;background:#2a303a;color:#cdd4df}}.rising,.emerging,.revived{{outline:1px solid #7087c9}}.cooling,.dormant{{opacity:.72}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px 7px;text-align:left;border-bottom:1px solid #2d323b;font-size:.86rem}}ul,ol{{line-height:1.55;color:#c8cdd5;padding-left:22px}}.blueprint p{{line-height:1.5}}.note{{border-left:4px solid #9aacff}}
@media(max-width:820px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="hero">
<div class="muted">Profile Library · {html.escape(str(identity.get("profile_label") or "Profile"))} · {html.escape(str(identity.get("profile_short_id") or ""))}</div>
<h1>{html.escape(str(profile.get("behavior_profile_name") or "Profile đang hình thành"))}</h1>{candidate_note}
<p class="muted">Longitudinal Recommendation/Exposure Profile: Home + Up Next + Subscriptions + daily decay. Đây là mô hình nghiên cứu của dự án, không phải hồ sơ nội bộ của YouTube.</p>
<div class="stats">
<div class="stat">Certainty<strong>{pct(profile.get("certainty_score")):.1f}%</strong></div>
<div class="stat">Daily history<strong>{int(temporal.get("daily_observation_count") or 0)}</strong></div>
<div class="stat">Home items<strong>{int(evidence.get("home_items") or 0)}</strong></div>
<div class="stat">Up Next replay<strong>{int(evidence.get("up_next_replay_count") or 0)}</strong></div>
<div class="stat">Sub videos<strong>{int(evidence.get("subscription_items") or 0)}</strong></div>
<div class="stat">Sub channels<strong>{int(evidence.get("subscription_channels_observed") or 0)}</strong></div>
</div></section>

<div class="grid"><section class="panel"><h2>Trọng số hồ sơ theo thời gian</h2>{bars or '<p class="muted">Chưa đủ dữ liệu.</p>'}</section>
<section class="panel note"><h2>Cách đọc</h2><ul><li><b>Today</b>: observation mới nhất trong ngày.</li><li><b>7d / 30d / Long</b>: rolling windows có exponential decay.</li><li><b>rising/emerging/revived</b>: tín hiệu đáng theo dõi để mở bridge/expansion.</li><li><b>cooling/dormant</b>: không nên pivot creator strategy chỉ dựa vào trọng số lịch sử.</li><li>Subscriptions là explicit affinity, không phải watch history.</li></ul></section></div>

<section class="panel"><h2>Chuỗi nội dung đề xuất</h2><div class="cards">{phase_cards or '<p class="muted">Chưa đủ dữ liệu.</p>'}</div></section>
<section class="panel"><h2>Creative brief cho video mới</h2><div class="cards">{''.join(blueprint_cards) or '<p class="muted">Chưa đủ dữ liệu.</p>'}</div></section>

<div class="grid"><section class="panel"><h2>Keyword trends</h2><table><thead><tr><th>Keyword</th><th>Trend</th><th>Today</th><th>7d</th><th>30d</th></tr></thead><tbody>{keyword_rows}</tbody></table></section>
<section class="panel"><h2>Tag trends</h2><table><thead><tr><th>Tag</th><th>Trend</th><th>Today</th><th>7d</th><th>30d</th></tr></thead><tbody>{tag_rows}</tbody></table></section></div>

<section class="panel"><h2>Observed subscribed channels</h2><p class="muted">Chỉ ghi nhận channel nhìn thấy trong snapshot read-only. Vắng mặt không được suy luận là đã unsubscribe.</p><table><thead><tr><th>Channel</th><th>Today</th><th>Days seen</th><th>First</th><th>Last</th></tr></thead><tbody>{channel_rows}</tbody></table></section>
<section class="panel"><h2>Up Next ổn định qua replay</h2><table><thead><tr><th>Video</th><th>Appear</th><th>Mean pos</th></tr></thead><tbody>{stable_rows}</tbody></table></section>
<section class="panel note"><h2>Guardrails</h2><ul>{''.join(f'<li>{html.escape(str(x))}</li>' for x in profile.get("channel_focus_guardrails") or [])}</ul></section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_profile")
    parser.add_argument("session_index")
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--html-output", required=True)
    parser.add_argument("--library-output", required=True)
    parser.add_argument("--history-output", required=True)
    parser.add_argument("--daily-dir", required=True)
    parser.add_argument("--previous-profile", default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    session_profile_path = resolve(args.session_profile)
    session_index_path = resolve(args.session_index)
    json_path = resolve(args.json_output)
    html_path = resolve(args.html_output)
    library_path = resolve(args.library_output)
    history_path = resolve(args.history_output)
    daily_dir = resolve(args.daily_dir)
    previous_path = resolve(args.previous_profile) if args.previous_profile else None

    session_profile = read_json(session_profile_path)
    session = read_json(session_index_path)
    previous_profile = None
    if previous_path and previous_path.exists():
        try:
            previous_profile = read_json(previous_path)
        except (OSError, json.JSONDecodeError):
            previous_profile = None

    profile = build_temporal_profile(repo_root, session_profile, session, daily_dir, previous_profile)
    write_json(json_path, profile)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(profile), encoding="utf-8")
    write_json(library_path, profile)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(profile, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(f"Temporal profile JSON -> {json_path}")
    print(f"Temporal profile HTML -> {html_path}")
    print(f"Daily observations -> {daily_dir}")


if __name__ == "__main__":
    main()
