#!/usr/bin/env python3
"""Build one creator-facing community report from sanitized profile submissions.

The central unit is a consenting participant, not a raw observation row. A
participant may contribute multiple browser/device profiles; their total weight
is capped and divided across those profiles so one operator with many profiles
does not automatically dominate the community signal.

This report describes fit/coverage inside the observed community panel. It is
not a probability that YouTube will recommend a video or that a viewer will
watch it.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MATCH_THRESHOLD = 0.08
USABLE_CERTAINTY = 0.30
POSITIVE_TRENDS = {"rising", "emerging", "revived"}
STABLE_TRENDS = {"stable", "baseline"}
NEGATIVE_TRENDS = {"cooling", "dormant"}
TREND_VALUE = {
    "rising": 1.0,
    "emerging": 0.85,
    "revived": 0.80,
    "stable": 0.55,
    "baseline": 0.50,
    "cooling": 0.20,
    "dormant": 0.05,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", text).strip()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def profile_quality(profile: dict) -> float:
    certainty = clamp(float(profile.get("certainty_score") or 0.0))
    days = max(0, int(profile.get("daily_observation_count") or 0))
    maturity = 0.55 + 0.45 * min(1.0, days / 7.0)
    return max(0.08, certainty * maturity)


def load_profiles(input_dir: Path) -> list[dict]:
    profiles = []
    if not input_dir.exists():
        return profiles
    for path in sorted(input_dir.glob("*.json")):
        try:
            row = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not row.get("participant_id") or not row.get("profile_key"):
            continue
        if not isinstance(row.get("interest_weights"), list) or not row.get("interest_weights"):
            continue
        row["_source_path"] = str(path)
        profiles.append(row)
    return profiles


def usable_profiles(profiles: list[dict]) -> list[dict]:
    return [
        row
        for row in profiles
        if float(row.get("certainty_score") or 0.0) >= USABLE_CERTAINTY
        and bool(row.get("interest_weights"))
    ]


def participant_balanced_weights(profiles: list[dict]) -> dict[str, float]:
    """Return profile_key -> weight, with every participant contributing equally."""
    by_participant: dict[str, list[dict]] = defaultdict(list)
    for profile in profiles:
        by_participant[str(profile.get("participant_id"))].append(profile)
    participant_count = len(by_participant)
    if participant_count == 0:
        return {}

    result: dict[str, float] = {}
    participant_share = 1.0 / participant_count
    for rows in by_participant.values():
        qualities = [profile_quality(row) for row in rows]
        quality_total = sum(qualities)
        if quality_total <= 0:
            quality_total = float(len(rows))
            qualities = [1.0] * len(rows)
        for row, quality in zip(rows, qualities):
            result[str(row.get("profile_key"))] = participant_share * quality / quality_total
    return result


def interest_map(profile: dict) -> dict[str, dict]:
    output = {}
    for row in profile.get("interest_weights") or []:
        cid = str(row.get("id") or "").strip()
        if cid:
            output[cid] = row
    return output


def aggregate_terms(
    matched_profiles: list[dict],
    weights: dict[str, float],
    field: str,
    *,
    positive_only: bool = False,
    limit: int = 12,
) -> list[dict]:
    score: dict[str, float] = defaultdict(float)
    support_profiles: dict[str, set[str]] = defaultdict(set)
    support_participants: dict[str, set[str]] = defaultdict(set)
    display: dict[str, str] = {}
    trend_score: dict[str, float] = defaultdict(float)

    for profile in matched_profiles:
        pkey = str(profile.get("profile_key"))
        participant = str(profile.get("participant_id"))
        pweight = float(weights.get(pkey, 0.0))
        if pweight <= 0:
            continue
        seen = set()
        for row in profile.get(field) or []:
            value = str(row.get("value") or "").strip()
            key = norm(value)
            if not key or key in seen:
                continue
            seen.add(key)
            trend = str(row.get("trend_state") or "baseline")
            if positive_only and trend not in POSITIVE_TRENDS:
                continue
            term_weight = clamp(float(row.get("weight") or 0.0))
            if term_weight <= 0:
                continue
            display[key] = value
            score[key] += pweight * term_weight
            trend_score[key] += pweight * TREND_VALUE.get(trend, 0.45)
            support_profiles[key].add(pkey)
            support_participants[key].add(participant)

    rows = []
    for key, value in score.items():
        rows.append(
            {
                "value": display.get(key, key),
                "score": round(value, 6),
                "profile_support": len(support_profiles[key]),
                "participant_support": len(support_participants[key]),
                "trend_strength": round(trend_score[key], 6),
            }
        )
    rows.sort(
        key=lambda row: (
            row["participant_support"],
            row["profile_support"],
            row["score"],
            row["trend_strength"],
        ),
        reverse=True,
    )
    return rows[:limit]


def aggregate_intents(matched_profiles: list[dict], weights: dict[str, float]) -> list[dict]:
    scores: dict[str, float] = defaultdict(float)
    labels: dict[str, str] = {}
    for profile in matched_profiles:
        pweight = float(weights.get(str(profile.get("profile_key")), 0.0))
        for row in profile.get("intent_weights") or []:
            iid = str(row.get("id") or "").strip()
            if not iid:
                continue
            labels[iid] = str(row.get("label") or iid)
            scores[iid] += pweight * clamp(float(row.get("weight") or 0.0))
    total = sum(scores.values())
    if total <= 0:
        return []
    rows = [
        {"id": iid, "label": labels.get(iid, iid), "weight": round(value / total, 4)}
        for iid, value in scores.items()
    ]
    rows.sort(key=lambda row: row["weight"], reverse=True)
    return rows


def build_report(profiles: list[dict]) -> dict:
    usable = usable_profiles(profiles)
    all_participants = {str(row.get("participant_id")) for row in profiles}
    usable_participants = {str(row.get("participant_id")) for row in usable}
    weights = participant_balanced_weights(usable)

    category_names: dict[str, str] = {}
    categories: set[str] = set()
    maps = {}
    for profile in usable:
        pkey = str(profile.get("profile_key"))
        maps[pkey] = interest_map(profile)
        for cid, row in maps[pkey].items():
            categories.add(cid)
            category_names.setdefault(cid, str(row.get("name_vi") or cid))

    lane_rows = []
    for cid in categories:
        matched = []
        matched_participants = set()
        weighted_interest = 0.0
        weighted_coverage = 0.0
        positive_weight = 0.0
        stable_weight = 0.0
        negative_weight = 0.0
        trend_profiles = defaultdict(int)

        for profile in usable:
            pkey = str(profile.get("profile_key"))
            pweight = float(weights.get(pkey, 0.0))
            row = maps[pkey].get(cid)
            if not row:
                continue
            interest = clamp(float(row.get("predicted_weight") or 0.0))
            weighted_interest += pweight * interest
            trend = str(row.get("trend_state") or "baseline")
            if interest >= MATCH_THRESHOLD:
                matched.append(profile)
                matched_participants.add(str(profile.get("participant_id")))
                weighted_coverage += pweight
                trend_profiles[trend] += 1
                if trend in POSITIVE_TRENDS:
                    positive_weight += pweight
                elif trend in NEGATIVE_TRENDS:
                    negative_weight += pweight
                else:
                    stable_weight += pweight

        if not matched:
            continue

        raw_profile_coverage = len(matched) / max(1, len(usable))
        participant_coverage = len(matched_participants) / max(1, len(usable_participants))
        trend_momentum = clamp(
            (positive_weight + 0.55 * stable_weight + 0.10 * negative_weight)
            / max(1e-9, weighted_coverage)
        )
        opportunity = clamp(
            0.42 * weighted_coverage
            + 0.28 * participant_coverage
            + 0.18 * min(1.0, weighted_interest / 0.25)
            + 0.12 * trend_momentum
        )

        core_keywords = aggregate_terms(matched, weights, "keyword_trends", limit=12)
        core_tags = aggregate_terms(matched, weights, "tag_trends", limit=12)
        expansion_keywords = aggregate_terms(
            matched,
            weights,
            "keyword_trends",
            positive_only=True,
            limit=12,
        )
        core_norm = {norm(row["value"]) for row in core_keywords[:6]}
        expansion_keywords = [row for row in expansion_keywords if norm(row["value"]) not in core_norm][:8]
        intents = aggregate_intents(matched, weights)
        top_intent = intents[0] if intents else None
        segment_key = cid + (f"::{top_intent['id']}" if top_intent else "")

        if opportunity >= 0.67 and participant_coverage >= 0.50:
            band = "strong"
        elif opportunity >= 0.45:
            band = "promising"
        elif opportunity >= 0.28:
            band = "experimental"
        else:
            band = "weak"

        lane_rows.append(
            {
                "segment_key": segment_key,
                "category_id": cid,
                "category_name_vi": category_names.get(cid, cid),
                "top_intent": top_intent,
                "matched_profile_count": len(matched),
                "matched_participant_count": len(matched_participants),
                "profile_coverage_ratio": round(raw_profile_coverage, 4),
                "participant_coverage_ratio": round(participant_coverage, 4),
                "participant_balanced_coverage": round(weighted_coverage, 4),
                "participant_balanced_interest": round(weighted_interest, 4),
                "trend_momentum": round(trend_momentum, 4),
                "trend_profile_counts": dict(sorted(trend_profiles.items())),
                "community_opportunity_score": round(opportunity, 4),
                "fit_band": band,
                "core_keywords": core_keywords,
                "core_tags": core_tags,
                "expansion_keywords": expansion_keywords,
                "interpretation": (
                    "Heuristic fit/coverage inside the consenting observed community panel; "
                    "not a probability of recommendation, impression, view, or external audience reach."
                ),
            }
        )

    lane_rows.sort(
        key=lambda row: (
            row["community_opportunity_score"],
            row["matched_participant_count"],
            row["participant_balanced_coverage"],
        ),
        reverse=True,
    )

    return {
        "version": "1.0.0",
        "report_type": "creator_community_intelligence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "community": {
            "participant_count": len(all_participants),
            "profile_count": len(profiles),
            "usable_participant_count": len(usable_participants),
            "usable_profile_count": len(usable),
            "participant_balance_rule": (
                "Each participant contributes equal total weight; multiple profiles belonging "
                "to the same participant divide that participant's weight according to profile quality."
            ),
            "minimum_profile_certainty": USABLE_CERTAINTY,
        },
        "creator_opportunities": lane_rows,
        "creator_summary": {
            "recommended_anchor": lane_rows[0] if lane_rows else None,
            "recommended_bridge": lane_rows[1] if len(lane_rows) > 1 else None,
            "controlled_expansion": next(
                (
                    row
                    for row in lane_rows[2:]
                    if row["trend_profile_counts"].get("rising", 0)
                    or row["trend_profile_counts"].get("emerging", 0)
                    or row["trend_profile_counts"].get("revived", 0)
                ),
                lane_rows[2] if len(lane_rows) > 2 else None,
            ),
        },
        "limitations": [
            "The community panel is not a representative sample of all YouTube users unless recruitment makes it so.",
            "More profile rows do not automatically mean more independent people; participant balancing is applied.",
            "Coverage and opportunity scores are project heuristics, not probabilities of views or recommendation.",
            "Only sanitized profile summaries are expected here; account credentials/cookies are outside this protocol.",
        ],
    }


def render_html(report: dict) -> str:
    community = report.get("community") or {}
    lanes = report.get("creator_opportunities") or []

    cards = []
    for rank, lane in enumerate(lanes[:12], start=1):
        keywords = ", ".join(str(x.get("value")) for x in lane.get("core_keywords") or [] if x.get("value"))
        tags = ", ".join(str(x.get("value")) for x in lane.get("core_tags") or [] if x.get("value"))
        expansions = ", ".join(str(x.get("value")) for x in lane.get("expansion_keywords") or [] if x.get("value"))
        intent = lane.get("top_intent") or {}
        cards.append(
            '<article>'
            f'<small>#{rank} · {html.escape(str(lane.get("fit_band") or ""))} · '
            f'Opportunity {float(lane.get("community_opportunity_score") or 0):.2f}</small>'
            f'<h3>{html.escape(str(lane.get("category_name_vi") or lane.get("category_id") or ""))}</h3>'
            f'<p><b>Community key:</b> {html.escape(str(lane.get("segment_key") or ""))}</p>'
            f'<p><b>Profiles:</b> {int(lane.get("matched_profile_count") or 0)} · '
            f'<b>Participants:</b> {int(lane.get("matched_participant_count") or 0)}</p>'
            f'<p><b>Participant coverage:</b> {float(lane.get("participant_coverage_ratio") or 0)*100:.1f}% · '
            f'<b>Balanced coverage:</b> {float(lane.get("participant_balanced_coverage") or 0)*100:.1f}%</p>'
            + (f'<p><b>Intent:</b> {html.escape(str(intent.get("label") or intent.get("id") or ""))}</p>' if intent else '')
            + f'<p><b>Core keys:</b> {html.escape(keywords or "—")}</p>'
            + f'<p><b>Tags:</b> {html.escape(tags or "—")}</p>'
            + f'<p><b>Keys mở rộng:</b> {html.escape(expansions or "—")}</p>'
            + '</article>'
        )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Creator Community Intelligence</title>
<style>
body{{margin:0;background:#0f1115;color:#f4f6f8;font-family:Inter,system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px 18px 60px}}
.hero,.panel,article{{background:#171a20;border:1px solid #30343d;border-radius:18px}}.hero,.panel{{padding:20px;margin-bottom:16px}}h1,h2,h3{{margin:.2em 0 .6em}}
.muted,small{{color:#aab1bd}}.stats,.cards{{display:grid;gap:12px}}.stats{{grid-template-columns:repeat(auto-fit,minmax(155px,1fr))}}.cards{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.stat,article{{background:#20242c;padding:14px;border-radius:14px}}.stat strong{{display:block;font-size:1.45rem;margin-top:4px}}article p{{line-height:1.48}}.note{{border-left:4px solid #9aacff}}
</style></head><body><main>
<section class="hero"><div class="muted">YouTube Library · Community panel</div><h1>Creator Community Intelligence</h1>
<p class="muted">Tổng hợp profile của những người tham gia theo participant-balanced weighting. Đây là audience-fit trong panel quan sát, không phải xác suất YouTube recommendation/view.</p>
<div class="stats">
<div class="stat">Participants<strong>{int(community.get("participant_count") or 0)}</strong></div>
<div class="stat">Profiles<strong>{int(community.get("profile_count") or 0)}</strong></div>
<div class="stat">Usable participants<strong>{int(community.get("usable_participant_count") or 0)}</strong></div>
<div class="stat">Usable profiles<strong>{int(community.get("usable_profile_count") or 0)}</strong></div>
</div></section>
<section class="panel"><h2>Hướng nội dung có coverage tốt trong cộng đồng</h2><div class="cards">{''.join(cards) or '<p class="muted">Chưa có đủ profile submissions.</p>'}</div></section>
<section class="panel note"><h2>Cách đọc</h2><p>Mỗi người tham gia có tổng trọng số như nhau; nếu một người có nhiều profile thì các profile đó chia nhau trọng số. Core keys/tags là cụm lặp trong các profile phù hợp. Keys mở rộng ưu tiên các cụm đang rising/emerging/revived. Không diễn giải các score thành xác suất view.</p></section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/community_profiles")
    parser.add_argument("--json-output", default="data/community_reports/current.json")
    parser.add_argument("--html-output", default="data/community_reports/current.html")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    profiles = load_profiles(resolve(args.input_dir))
    report = build_report(profiles)
    json_path = resolve(args.json_output)
    html_path = resolve(args.html_output)
    write_json(json_path, report)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(report), encoding="utf-8")
    print(f"Community report -> {json_path}")
    print(f"Community HTML -> {html_path}")
    print(f"Participants -> {report['community']['participant_count']}")
    print(f"Profiles -> {report['community']['profile_count']}")


if __name__ == "__main__":
    main()
