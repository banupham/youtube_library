# Longitudinal Profile Model — Phase 5.5

## Purpose

Phase 5.5 turns a one-session recommendation profile into a longitudinal profile that can change gradually over time.

The model keeps three evidence classes separate:

```text
Recommendation exposure
├── Home
└── Up Next

Explicit affinity
└── Subscriptions

Historical state
└── Daily observations
```

This is a project research model. It is not a reconstruction of YouTube's internal user profile or ranking system.

## Collection cadence

Default research cadence:

```text
1 browser profile
→ 1 collection session per calendar day
```

The extension does not create YouTube interactions. It only reads Home, fetches watch-page HTML for Up Next evidence, and reads Subscriptions pages.

If a profile is collected multiple times on the same day, the newest collection replaces that day's daily observation. Raw session/surface evidence remains available for debugging, but one calendar day counts as one longitudinal observation.

## Surfaces

### Home

Interpretation: profile-level recommendation exposure prior.

### Up Next

Interpretation: context-specific recommendation neighborhood around sampled Home seeds.

Repeated requests are normalized by seed/replay so a large number of replay observations cannot overwhelm Home just because there are more rows.

### Subscriptions

Two read-only sources are collected:

- `/feed/subscriptions`: videos currently exposed from subscribed channels; these videos can be enriched and classified.
- `/feed/channels`: subscribed channels visible in the initial read-only page payload.

Subscriptions are treated as explicit-affinity evidence, not watch history.

Absence of a channel from one snapshot must **not** be interpreted as an unsubscribe because the initial page payload may be incomplete or paginated.

## Surface priors

When all three category distributions are available, the current project heuristic starts with:

```text
Home           0.53
Up Next        0.32
Subscriptions  0.15
```

If one surface is unavailable, the available priors are renormalized rather than assigning zero evidence to the whole profile.

These numbers are research parameters and must remain configurable in future versions.

## Daily state

Per-profile daily state is stored under:

```text
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
```

Each daily observation contains:

- surface weights actually applied;
- category/interest weights;
- per-surface category support;
- keyword weights;
- tag weights;
- observed subscribed channels;
- source item counts;
- candidate behavior-profile name.

## Temporal windows

The model exposes:

```text
Today
7 days
30 days
Long term
```

Each rolling window uses exponential decay:

```text
weight(age) = 0.5 ** (age_days / half_life_days)
```

Initial parameters:

```text
7d         half-life 3.5 days
30d        half-life 14 days
long-term  half-life 60 days
```

The current profile weight starts from:

```text
0.50 × Today
+ 0.30 × 7d
+ 0.15 × 30d
+ 0.05 × Long term
```

This prevents one daily snapshot from completely replacing an established profile while still allowing genuinely new interests to rise.

## Trend states

Interest rows can have:

```text
baseline
emerging
rising
stable
cooling
dormant
revived
```

Definitions are heuristic and based on repeated daily observations, not YouTube labels.

### baseline

Not enough earlier daily observations to estimate change.

### emerging

A meaningful interest has appeared for only a small number of recent observation days.

### rising

Today's weight is materially higher than the recent previous-window baseline.

### stable

No sufficiently strong upward/downward change is detected.

### cooling

Today's weight is materially lower than the recent previous-window baseline.

### dormant

The interest remains in 30-day history but is nearly absent today.

### revived

An interest reappears after a meaningful gap.

## Profile-name stability

The human-readable profile name must not flip after one unusual feed.

The system keeps:

```text
stable_name
candidate_name
candidate_consecutive_days
previous_names
```

An existing stable name is replaced only when a new candidate persists for three consecutive daily observations.

The name is always a project research label; it is not claimed to be a YouTube internal label.

## Creator strategy impact

Creator strategy should prefer:

```text
stable / rising anchor
→ cross-surface bridge
→ emerging/revived controlled expansion
```

Cooling or dormant interests should normally not trigger a channel pivot.

Opportunity scoring may use temporal momentum as one component, but remains a heuristic research score and never a promise of impressions or views.

## Keyword and tag trends

Keywords and tags also receive Today / 7d / 30d / Long-term weights.

Use them to understand semantic continuity and packaging language around the observed profile.

Do not infer:

```text
same tags → guaranteed recommendation
```

Tags must remain truthful to the actual creator video.

## Current profile output

The user-facing files remain one current pair per browser profile:

```text
data/profile_reports/profile_<id>__current.profile.json
data/profile_reports/profile_<id>__current.profile.html
```

The persistent machine state is:

```text
data/profile_library/profile_<id>.json
data/profile_library/profile_<id>.history.jsonl
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
```

## Safety boundary

All real YouTube collection remains read-only.

The project must not automatically click, play, like, comment, subscribe, unsubscribe, or create fake engagement/traffic.

Viewer Robot phases after this point remain synthetic/offline.
