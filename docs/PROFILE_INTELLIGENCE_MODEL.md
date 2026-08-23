# Profile Intelligence Model

## Goal

The project does not assume it knows a viewer's true preferences.
It estimates a **recommendation prior** from what YouTube currently exposes to a profile, then reduces uncertainty as more evidence arrives.

This model is useful even for a cold-start/new profile: the first recommendation surfaces already provide a distribution of content hypotheses that YouTube is willing to show.

## Stage 1 — Recommendation Prior

Current source: **YouTube Home**.

For every exposed video we collect, when available:

- recommendation position
- title and channel
- description
- creator tags
- hashtags
- YouTube category
- YouTube topic details
- publish time
- public views / likes / comments
- internal content classification
- content intent
- target profile
- popularity/demand signal

Higher-ranked recommendations receive more exposure weight.
Low-confidence classifications receive less weight.
Creator tags are downweighted when they are weakly supported by title, description, or topic metadata.

The output is a prior, not watch-history truth.

## Required output

Each snapshot must produce:

1. `predicted_interest_weights`
   - probability-like weights for content families
   - `core`, `adjacent`, or `exploration` zone

2. `content_directions`
   - predicted profile fit
   - demand signal
   - freshness signal
   - metadata coherence
   - heuristic opportunity score
   - dominant content intent
   - representative videos

3. `keyword_map`
   - creator tags
   - hashtags
   - YouTube topics
   - classifier evidence phrases

4. `creator_tag_map`
   - observed tags around the recommendation profile
   - support count
   - content-consistency score

5. `expansion_candidates`
   - non-core videos shown high enough in the recommendation surface to be plausible exploration/expansion hypotheses

6. `evidence_quality`
   - classified/enriched coverage
   - certainty / uncertainty
   - behavior evidence availability

## Interpretation

### Core

Content families strongly and repeatedly represented in the current recommendation exposure.

### Adjacent

Content families close to the core and plausibly sharing audience context.

### Exploration

Lower-weight hypotheses that may represent YouTube broadening or testing the profile.
This is an inference, not an internal YouTube label.

### Opportunity score

A heuristic blend of:

- relative profile fit
- public demand signal
- freshness
- metadata coherence

It is used to rank content experiments. It is **not** a promise or probability of impressions/views.

## Stage 2 — Multiple recommendation surfaces

Do not silently merge different surfaces.
Each surface should be collected as separate evidence:

- Home
- Up Next / Next video
- Watch-page recommendation rail
- Search/result surfaces when relevant
- Subscriptions or other surfaces if explicitly modeled

Future aggregation can use surface-specific weights.
For example, an Up Next recommendation after a selected seed video is more context-specific than a generic Home recommendation.

## Stage 3 — Behavior posterior

Once the project has simulated or observed allowed interaction evidence, update the prior with:

- skip
- click
- watch duration
- completion
- rewatch
- like/save when part of the simulation model

Conceptually:

```text
Recommendation prior
        +
Behavior evidence
        +
Repeated snapshots
        +
Additional surfaces
        ↓
Updated profile posterior
```

The profile should become more specific over time:

```text
Category
→ Niche
→ Topic
→ Subtopic
→ Keywords
```

## Creator-side use

The creator-side output should answer:

- What content families is this profile currently exposed to?
- What appears core vs adjacent vs exploratory?
- Which keywords/topics/tags recur around those videos?
- Which directions combine profile fit and current demand?
- Which content experiment should be tested first?

The system should use tags as semantic/targeting evidence, not as a recommendation-control mechanism.
