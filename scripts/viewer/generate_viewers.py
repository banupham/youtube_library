#!/usr/bin/env python3
"""Generate structured synthetic Viewer Robots for offline simulation.

Phase 6 supports two seed modes:

1. pure_synthetic
   Build a viewer from the project taxonomy + seed interest relationship graph.

2. observed_profile_prior
   Build a synthetic cohort around one longitudinal observed profile. The
   observed profile is only a prior; generated viewers are offline simulation
   entities and never perform actions on YouTube.

This module intentionally stops before feed ranking and interaction simulation.
Those belong to Phases 7 and 8.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

INTENT_IDS = [
    "tutorial",
    "review",
    "news",
    "livestream",
    "compilation",
    "documentary",
    "entertainment",
    "analysis",
]

CATEGORY_INTENT_PRIORS = {
    "education": {"tutorial": 1.8, "documentary": 1.3, "analysis": 1.1},
    "science_technology": {"tutorial": 1.8, "review": 1.3, "analysis": 1.3},
    "gaming": {"livestream": 1.5, "analysis": 1.4, "entertainment": 1.3, "review": 1.1},
    "music": {"compilation": 1.8, "livestream": 1.2, "entertainment": 1.2},
    "news_politics": {"news": 2.0, "analysis": 1.5, "documentary": 1.1},
    "sports": {"analysis": 1.4, "livestream": 1.3, "news": 1.2},
    "film_animation": {"entertainment": 1.4, "analysis": 1.2, "documentary": 1.1},
    "entertainment": {"entertainment": 1.8, "compilation": 1.2, "livestream": 1.1},
    "comedy": {"entertainment": 2.0, "compilation": 1.1},
    "howto_style": {"tutorial": 2.0, "review": 1.1},
    "business_finance": {"analysis": 1.5, "tutorial": 1.3, "news": 1.1},
    "travel_events": {"documentary": 1.2, "review": 1.2, "entertainment": 1.2},
    "autos_vehicles": {"review": 1.6, "tutorial": 1.2, "analysis": 1.1},
    "health_fitness": {"tutorial": 1.5, "documentary": 1.1, "review": 1.1},
    "food_cooking": {"tutorial": 1.5, "entertainment": 1.2, "review": 1.1},
    "people_lifestyle": {"entertainment": 1.3, "documentary": 1.1, "tutorial": 1.0},
    "pets_animals": {"entertainment": 1.3, "tutorial": 1.1, "documentary": 1.1},
    "society_community": {"documentary": 1.4, "analysis": 1.2, "news": 1.1},
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize(values: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in values.values())
    if total <= 0:
        return {}
    return {key: max(0.0, float(value)) / total for key, value in values.items() if float(value) > 0}


def entropy01(vector: dict[str, float]) -> float:
    probs = [value for value in vector.values() if value > 0]
    if len(probs) <= 1:
        return 0.0
    entropy = -sum(p * math.log(p) for p in probs)
    return clamp(entropy / math.log(len(probs)), 0.0, 1.0)


def derive_seed(master_seed: int, *parts: object) -> int:
    raw = "|".join([str(master_seed), *[str(part) for part in parts]])
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def stable_id(prefix: str, *parts: object, length: int = 16) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def load_categories(path: Path) -> dict[str, dict]:
    payload = read_json(path)
    categories = {}
    for row in payload.get("categories") or []:
        cid = str(row.get("id") or "").strip()
        if cid:
            categories[cid] = {
                "id": cid,
                "name_vi": str(row.get("name_vi") or cid),
            }
    if not categories:
        raise ValueError(f"No categories found in {path}")
    return categories


def load_adjacency(path: Path, valid_ids: set[str]) -> dict[str, list[tuple[str, float]]]:
    payload = read_json(path)
    graph: dict[str, dict[str, float]] = defaultdict(dict)
    for edge in payload.get("edges") or []:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        weight = float(edge.get("weight") or 0.0)
        if source not in valid_ids or target not in valid_ids or source == target or weight <= 0:
            continue
        graph[source][target] = max(graph[source].get(target, 0.0), weight)
        if edge.get("bidirectional"):
            graph[target][source] = max(graph[target].get(source, 0.0), weight)
    return {
        source: sorted(targets.items(), key=lambda item: (-item[1], item[0]))
        for source, targets in graph.items()
    }


def weighted_sample_without_replacement(
    rng: random.Random,
    candidates: list[tuple[str, float]],
    count: int,
) -> list[str]:
    pool = [(key, max(0.0, float(weight))) for key, weight in candidates if float(weight) > 0]
    selected: list[str] = []
    for _ in range(min(count, len(pool))):
        total = sum(weight for _, weight in pool)
        if total <= 0:
            break
        needle = rng.random() * total
        running = 0.0
        chosen_index = len(pool) - 1
        for index, (_, weight) in enumerate(pool):
            running += weight
            if needle <= running:
                chosen_index = index
                break
        key, _ = pool.pop(chosen_index)
        selected.append(key)
    return selected


def intent_preferences(rng: random.Random, primary_id: str) -> dict[str, float]:
    priors = CATEGORY_INTENT_PRIORS.get(primary_id, {})
    raw = {}
    for intent_id in INTENT_IDS:
        prior = 0.65 * float(priors.get(intent_id, 1.0))
        raw[intent_id] = rng.gammavariate(max(0.25, prior), 1.0)
    normalized = normalize(raw)
    return {key: round(value, 6) for key, value in normalized.items()}


def partition_interests(
    vector: dict[str, float],
    categories: dict[str, dict],
    *,
    exploration_ids: set[str] | None = None,
    source_by_id: dict[str, str] | None = None,
) -> dict[str, list[dict]]:
    exploration_ids = exploration_ids or set()
    source_by_id = source_by_id or {}
    ordered = sorted(vector.items(), key=lambda item: (-item[1], item[0]))
    top = ordered[0][1] if ordered else 0.0

    primary: list[dict] = []
    secondary: list[dict] = []
    low: list[dict] = []
    exploration: list[dict] = []

    for index, (cid, weight) in enumerate(ordered):
        row = {
            "id": cid,
            "name_vi": categories.get(cid, {}).get("name_vi", cid),
            "weight": round(weight, 6),
            "source": source_by_id.get(cid, "generated"),
        }
        if cid in exploration_ids:
            exploration.append(row)
        elif index == 0 or (len(primary) < 2 and weight >= max(0.20, top * 0.62)):
            primary.append(row)
        elif weight >= max(0.055, top * 0.16):
            secondary.append(row)
        else:
            low.append(row)

    if not primary and ordered:
        cid, weight = ordered[0]
        primary.append(
            {
                "id": cid,
                "name_vi": categories.get(cid, {}).get("name_vi", cid),
                "weight": round(weight, 6),
                "source": source_by_id.get(cid, "generated"),
            }
        )
    return {
        "primary_interests": primary,
        "secondary_interests": secondary,
        "low_interests": low,
        "exploration_interests": exploration,
    }


def topic_vector_from_profile(profile: dict) -> dict[str, float]:
    raw = {}
    for row in profile.get("topic_map") or []:
        value = str(row.get("value") or "").strip()
        score = float(row.get("score") or 0.0)
        if value and score > 0:
            raw[value] = raw.get(value, 0.0) + score
    normalized = normalize(raw)
    return {key: round(value, 6) for key, value in normalized.items()}


def base_viewer(
    *,
    viewer_id: str,
    seed_source: str,
    viewer_seed: int,
    master_seed: int,
    viewer_index: int,
    vector: dict[str, float],
    categories: dict[str, dict],
    exploration_ids: set[str],
    source_by_id: dict[str, str],
    preferences: dict,
    lineage: dict,
    topic_vector: dict[str, float] | None = None,
) -> dict:
    groups = partition_interests(
        vector,
        categories,
        exploration_ids=exploration_ids,
        source_by_id=source_by_id,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "viewer_id": viewer_id,
        "seed_source": seed_source,
        "random_seed": viewer_seed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": {
            "generator_version": GENERATOR_VERSION,
            "master_seed": master_seed,
            "viewer_index": viewer_index,
            **lineage,
        },
        "interest_model": {
            "category_vector": {key: round(value, 6) for key, value in vector.items()},
            **groups,
            "topic_vector": topic_vector or {},
        },
        "preference_model": preferences,
        "simulation_state": {
            "step": 0,
            "interaction_count": 0,
            "last_video_id": None,
            "state_version": 0,
        },
    }


def generate_pure_synthetic(
    *,
    categories: dict[str, dict],
    adjacency: dict[str, list[tuple[str, float]]],
    master_seed: int,
    viewer_index: int,
    primary_override: str | None = None,
) -> dict:
    viewer_seed = derive_seed(master_seed, "pure_synthetic", viewer_index)
    rng = random.Random(viewer_seed)
    ids = sorted(categories)
    if primary_override:
        if primary_override not in categories:
            raise ValueError(f"Unknown primary category: {primary_override}")
        primary = primary_override
    else:
        primary = ids[rng.randrange(len(ids))]

    adjacent = adjacency.get(primary) or [(cid, 1.0) for cid in ids if cid != primary]
    secondary_count = rng.randint(1, min(3, len(adjacent)))
    secondary_ids = weighted_sample_without_replacement(rng, adjacent, secondary_count)

    excluded = {primary, *secondary_ids}
    remaining = [cid for cid in ids if cid not in excluded]
    exploration_count = 0
    roll = rng.random()
    if remaining and roll < 0.78:
        exploration_count = 1
    if len(remaining) >= 2 and roll < 0.16:
        exploration_count = 2
    rng.shuffle(remaining)
    exploration_ids = set(remaining[:exploration_count])

    low_candidates = [cid for cid in remaining if cid not in exploration_ids]
    rng.shuffle(low_candidates)
    low_ids = low_candidates[: rng.randint(1, min(3, len(low_candidates))) if low_candidates else 0]

    raw: dict[str, float] = {primary: rng.uniform(6.0, 9.5)}
    edge_weights = dict(adjacent)
    for cid in secondary_ids:
        raw[cid] = rng.uniform(1.5, 3.0) * (0.65 + edge_weights.get(cid, 0.5))
    for cid in exploration_ids:
        raw[cid] = rng.uniform(0.25, 0.75)
    for cid in low_ids:
        raw[cid] = rng.uniform(0.10, 0.45)

    vector = normalize(raw)
    diversity = entropy01(vector)
    exploration_rate = clamp(0.05 + 0.20 * diversity + rng.uniform(-0.025, 0.04), 0.04, 0.30)
    novelty_tolerance = clamp(0.08 + 0.34 * diversity + rng.uniform(-0.04, 0.06), 0.05, 0.58)
    stability_preference = clamp(0.92 - 0.65 * exploration_rate + rng.uniform(-0.04, 0.04), 0.48, 0.96)

    source_by_id = {primary: "primary_seed"}
    source_by_id.update({cid: "relationship_graph" for cid in secondary_ids})
    source_by_id.update({cid: "exploration_sample" for cid in exploration_ids})
    source_by_id.update({cid: "low_interest_noise" for cid in low_ids})

    viewer_id = stable_id("viewer", "pure_synthetic", master_seed, viewer_index)
    return base_viewer(
        viewer_id=viewer_id,
        seed_source="pure_synthetic",
        viewer_seed=viewer_seed,
        master_seed=master_seed,
        viewer_index=viewer_index,
        vector=vector,
        categories=categories,
        exploration_ids=exploration_ids,
        source_by_id=source_by_id,
        preferences={
            "exploration_rate": round(exploration_rate, 6),
            "novelty_tolerance": round(novelty_tolerance, 6),
            "diversity_preference": round(diversity, 6),
            "stability_preference": round(stability_preference, 6),
            "intent_preferences": intent_preferences(rng, primary),
        },
        lineage={
            "source_profile_id": None,
            "source_profile_short_id": None,
            "source_profile_name": None,
            "source_analysis_version": None,
            "primary_category_seed": primary,
            "relationship_graph_version": "1.0.0",
        },
    )


def profile_category_prior(profile: dict, valid_ids: set[str]) -> dict[str, float]:
    raw = {}
    for row in profile.get("interest_weights") or []:
        cid = str(row.get("id") or "")
        value = float(row.get("predicted_weight") or row.get("weight") or 0.0)
        if cid in valid_ids and value > 0:
            raw[cid] = raw.get(cid, 0.0) + value
    normalized = normalize(raw)
    if not normalized:
        raise ValueError("Observed profile has no usable interest_weights")
    return normalized


def profile_intent_prior(profile: dict) -> dict[str, float]:
    raw = {}
    for row in profile.get("intent_weights") or []:
        iid = str(row.get("id") or "")
        value = float(row.get("weight") or 0.0)
        if iid and value > 0:
            raw[iid] = raw.get(iid, 0.0) + value
    return normalize(raw)


def generate_observed_prior(
    *,
    profile: dict,
    categories: dict[str, dict],
    adjacency: dict[str, list[tuple[str, float]]],
    master_seed: int,
    viewer_index: int,
) -> dict:
    profile_identity = profile.get("profile") or profile.get("collector_profile") or {}
    source_profile_id = str(profile_identity.get("profile_id") or "observed-profile")
    source_short_id = str(profile_identity.get("profile_short_id") or "") or re.sub(r"[^A-Za-z0-9]", "", source_profile_id)[:8]
    source_name = str(profile.get("behavior_profile_name") or "Observed profile prior")
    source_token = source_profile_id or source_short_id or source_name

    viewer_seed = derive_seed(master_seed, "observed_profile_prior", source_token, viewer_index)
    rng = random.Random(viewer_seed)
    prior = profile_category_prior(profile, set(categories))
    certainty = clamp(float(profile.get("certainty_score") or 0.5), 0.0, 1.0)
    uncertainty = 1.0 - certainty
    prior_diversity = entropy01(prior)

    sigma = 0.06 + 0.22 * uncertainty
    perturbed = {
        cid: value * rng.lognormvariate(0.0, sigma)
        for cid, value in prior.items()
    }

    ordered_prior = sorted(prior.items(), key=lambda item: (-item[1], item[0]))
    top_ids = [cid for cid, _ in ordered_prior[:3]]
    candidate_weights: dict[str, float] = defaultdict(float)
    for source in top_ids:
        source_strength = prior.get(source, 0.0)
        for target, edge_weight in adjacency.get(source, []):
            if target not in prior or prior.get(target, 0.0) < 0.02:
                candidate_weights[target] += source_strength * edge_weight

    exploration_rate = clamp(
        0.05 + 0.22 * uncertainty + 0.10 * prior_diversity + rng.uniform(-0.02, 0.03),
        0.04,
        0.34,
    )
    novelty_tolerance = clamp(
        0.08 + 0.28 * prior_diversity + 0.14 * uncertainty + rng.uniform(-0.03, 0.05),
        0.05,
        0.58,
    )
    stability_preference = clamp(
        0.58 + 0.28 * certainty + 0.10 * (1.0 - exploration_rate) + rng.uniform(-0.03, 0.03),
        0.50,
        0.97,
    )

    exploration_ids: set[str] = set()
    if candidate_weights and rng.random() < (0.45 + 0.45 * exploration_rate):
        candidates = sorted(candidate_weights.items())
        selected = weighted_sample_without_replacement(rng, candidates, 1 if rng.random() < 0.85 else 2)
        exploration_ids.update(selected)
        noise_budget = clamp(0.025 + 0.18 * exploration_rate + 0.08 * uncertainty, 0.025, 0.14)
        for cid in list(perturbed):
            perturbed[cid] *= 1.0 - noise_budget
        selected_total = sum(candidate_weights[cid] for cid in selected) or 1.0
        for cid in selected:
            perturbed[cid] = perturbed.get(cid, 0.0) + noise_budget * candidate_weights[cid] / selected_total

    vector = normalize(perturbed)
    primary_id = max(vector, key=vector.get)
    intent_prior = profile_intent_prior(profile)
    if intent_prior:
        intent_noise = {
            iid: value * rng.lognormvariate(0.0, 0.05 + 0.12 * uncertainty)
            for iid, value in intent_prior.items()
        }
        intents = normalize(intent_noise)
        intent_output = {key: round(value, 6) for key, value in intents.items()}
    else:
        intent_output = intent_preferences(rng, primary_id)

    source_by_id = {cid: "observed_profile_prior" for cid in prior}
    source_by_id.update({cid: "adjacent_exploration" for cid in exploration_ids})

    viewer_id = stable_id("viewer", "observed_profile_prior", source_token, master_seed, viewer_index)
    return base_viewer(
        viewer_id=viewer_id,
        seed_source="observed_profile_prior",
        viewer_seed=viewer_seed,
        master_seed=master_seed,
        viewer_index=viewer_index,
        vector=vector,
        categories=categories,
        exploration_ids=exploration_ids,
        source_by_id=source_by_id,
        preferences={
            "exploration_rate": round(exploration_rate, 6),
            "novelty_tolerance": round(novelty_tolerance, 6),
            "diversity_preference": round(entropy01(vector), 6),
            "stability_preference": round(stability_preference, 6),
            "intent_preferences": intent_output,
        },
        lineage={
            "source_profile_id": source_profile_id,
            "source_profile_short_id": source_short_id or None,
            "source_profile_name": source_name,
            "source_analysis_version": profile.get("analysis_version"),
            "source_profile_certainty": round(certainty, 6),
            "relationship_graph_version": "1.0.0",
        },
        topic_vector=topic_vector_from_profile(profile),
    )


def validate_viewer(viewer: dict) -> list[str]:
    errors = []
    vector = (viewer.get("interest_model") or {}).get("category_vector") or {}
    total = sum(float(value) for value in vector.values())
    if not vector:
        errors.append("category_vector is empty")
    elif abs(total - 1.0) > 1e-5:
        errors.append(f"category_vector must sum to 1; got {total}")
    primary = (viewer.get("interest_model") or {}).get("primary_interests") or []
    if not primary:
        errors.append("primary_interests is empty")
    for field in ("exploration_rate", "novelty_tolerance", "diversity_preference", "stability_preference"):
        value = float((viewer.get("preference_model") or {}).get(field, -1))
        if not 0.0 <= value <= 1.0:
            errors.append(f"{field} outside [0,1]")
    if viewer.get("seed_source") not in {"pure_synthetic", "observed_profile_prior"}:
        errors.append("invalid seed_source")
    return errors


def build_batch(
    *,
    mode: str,
    count: int,
    master_seed: int,
    categories: dict[str, dict],
    adjacency: dict[str, list[tuple[str, float]]],
    profile: dict | None,
    primary: str | None,
) -> list[dict]:
    viewers = []
    for index in range(count):
        if mode == "pure_synthetic":
            viewer = generate_pure_synthetic(
                categories=categories,
                adjacency=adjacency,
                master_seed=master_seed,
                viewer_index=index,
                primary_override=primary,
            )
        else:
            if profile is None:
                raise ValueError("observed_profile_prior mode requires --profile")
            viewer = generate_observed_prior(
                profile=profile,
                categories=categories,
                adjacency=adjacency,
                master_seed=master_seed,
                viewer_index=index,
            )
        errors = validate_viewer(viewer)
        if errors:
            raise ValueError(f"Generated invalid viewer {viewer.get('viewer_id')}: {errors}")
        viewers.append(viewer)
    return viewers


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline Viewer Robot cohorts")
    parser.add_argument("--mode", choices=["pure_synthetic", "observed_profile_prior"], required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42, dest="master_seed")
    parser.add_argument("--profile", default=None, help="Longitudinal profile JSON for observed_profile_prior mode")
    parser.add_argument("--primary", default=None, help="Optional primary category ID for pure_synthetic mode")
    parser.add_argument("--output-dir", default="data/synthetic_viewers")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--categories", default="taxonomy/homepage_categories.v1.json")
    parser.add_argument("--relations", default="taxonomy/interest_relations.v1.json")
    args = parser.parse_args()

    if args.count < 1 or args.count > 100000:
        raise SystemExit("--count must be between 1 and 100000")
    if args.master_seed < 0:
        raise SystemExit("--seed must be >= 0")

    repo_root = Path(__file__).resolve().parents[2]

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    categories_path = resolve(args.categories)
    relations_path = resolve(args.relations)
    categories = load_categories(categories_path)
    adjacency = load_adjacency(relations_path, set(categories))

    profile = None
    profile_path = None
    if args.profile:
        profile_path = resolve(args.profile)
        profile = read_json(profile_path)
    if args.mode == "observed_profile_prior" and profile is None:
        raise SystemExit("--profile is required for observed_profile_prior mode")

    viewers = build_batch(
        mode=args.mode,
        count=args.count,
        master_seed=args.master_seed,
        categories=categories,
        adjacency=adjacency,
        profile=profile,
        primary=args.primary,
    )

    source_token = "none"
    if profile:
        identity = profile.get("profile") or profile.get("collector_profile") or {}
        source_token = str(identity.get("profile_id") or identity.get("profile_short_id") or profile_path or "observed")
    batch_id = args.batch_id or stable_id(
        "batch",
        args.mode,
        args.master_seed,
        args.count,
        source_token,
        args.primary or "auto",
        length=12,
    )

    output_root = resolve(args.output_dir)
    batch_dir = output_root / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    viewers_path = batch_dir / "viewers.jsonl"
    with viewers_path.open("w", encoding="utf-8") as handle:
        for viewer in viewers:
            handle.write(json.dumps(viewer, ensure_ascii=False, separators=(",", ":")) + "\n")

    manifest = {
        "version": "1.0.0",
        "batch_id": batch_id,
        "generator_version": GENERATOR_VERSION,
        "mode": args.mode,
        "master_seed": args.master_seed,
        "viewer_count": len(viewers),
        "source_profile": str(profile_path.relative_to(repo_root)) if profile_path and profile_path.is_relative_to(repo_root) else str(profile_path) if profile_path else None,
        "primary_override": args.primary,
        "categories": str(categories_path.relative_to(repo_root)) if categories_path.is_relative_to(repo_root) else str(categories_path),
        "relations": str(relations_path.relative_to(repo_root)) if relations_path.is_relative_to(repo_root) else str(relations_path),
        "schema": "schemas/viewer_robot.v1.schema.json",
        "viewers_file": "viewers.jsonl",
        "reproducibility": "Viewer IDs, seeds and model fields are deterministic for the same inputs/master seed. created_at timestamps may differ across runs.",
        "scope": "offline_simulation_only_no_youtube_actions",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(batch_dir / "manifest.json", manifest)

    print(f"Viewer batch -> {batch_dir}")
    print(f"Mode -> {args.mode}")
    print(f"Viewer count -> {len(viewers)}")
    print(f"Master seed -> {args.master_seed}")
    if profile_path:
        print(f"Observed prior -> {profile_path}")


if __name__ == "__main__":
    main()
