# Distributed Profile Collection Network

## Purpose

The project treats observed profile data as a **consenting community panel** rather than as a proxy for all YouTube users.

The network has three separate modules:

```text
PLATFORM COLLECTOR
(browser / Android adapter / future platforms)
        ↓
LOCAL PROFILE ENGINE
(Home + Up Next + Subscriptions + daily longitudinal state)
        ↓ sanitized summary only
COMMUNITY INGESTION + CREATOR AGGREGATOR
        ↓
Creator Community Intelligence
```

The creator-facing result is community-level, not a technical dump of every profile.

## 1. Participant vs profile

A participant is a real consenting project contributor. One participant may have one or more YouTube/browser profiles.

```text
Participant A
├── Profile A1
├── Profile A2
└── Profile A3

Participant B
└── Profile B1
```

The community engine does **not** count the example above as four independent people.

Each participant receives equal total community weight. Multiple profiles divide that participant's weight according to profile quality/certainty.

Reports always expose both:

```text
participant_count
profile_count
usable_participant_count
usable_profile_count
```

## 2. Platform Collector contract

A platform collector may collect only read-only evidence available to that participant and platform.

Current browser collector supports:

```text
Home recommendation exposure
Up Next recommendation exposure
Subscriptions feed / subscribed-channel affinity
daily longitudinal state
```

It does not automatically click, play, like, comment, subscribe, or create traffic.

### Participation / auto-start rule

Joining the project and installing the collector establishes participation at the application level. The participant does **not** need to enable a runtime checkbox every time.

Browser extension `0.6.1` uses:

```text
extension installed for a participating profile
        ↓
passive collection defaults ON
        ↓
participant opens/uses YouTube normally
        ↓
collector observes allowed surfaces automatically
        ↓
maximum configured daily snapshot cadence
```

The popup exposes only a **Pause collection / Resume collection** control. An explicit `false` state is preserved across browser restarts; otherwise passive collection is enabled by default.

The collector should not open videos or manufacture sessions solely to change recommendation state.

### Natural capture rule

Passive capture starts automatically when the participant visits YouTube, but it only captures surfaces the participant naturally reaches:

```text
Home opened naturally
→ passive Home snapshot

/watch?v=... opened naturally
→ passive Up Next snapshot

/feed/subscriptions opened naturally
→ passive Subscriptions snapshot
```

It does not auto-navigate, auto-scroll, or auto-play in passive mode.

## 3. Android participation

Android is an adapter to the same submission protocol, not a separate data model.

Important limitation: the public YouTube Data API does not expose a user's personalized Home recommendation feed. A native Android collector therefore must not claim it can reproduce browser Home/Up Next data unless a legitimate read-only interface has been validated.

Initial Android-compatible paths may include:

- read-only subscription/account metadata through officially authorized APIs where available;
- a dedicated web collector container controlled by the participant, if authentication and platform policy allow it;
- other explicit read-only surfaces added later.

Accessibility scraping of the native YouTube app is **not** the default design because it is invasive and can capture unrelated sensitive UI data.

Every Android adapter ultimately emits the same sanitized profile summary schema:

```text
schemas/community_profile_submission.v1.schema.json
```

## 4. Local profile engine

Raw recommendation data remains local by default.

The existing profile pipeline builds:

```text
Home + Up Next + Subscriptions
→ classifier/API enrichment
→ daily observation
→ Today / 7d / 30d / Long-term
→ trend states
→ current longitudinal profile
```

The community server does not need raw cookies, Google identities, or complete browsing history.

## 5. Sanitized submission

`scripts/community/submit_profile.py` converts the current longitudinal profile into a small community payload containing only fields needed for community analysis:

```text
random participant_id
random device_id
stable random-derived profile_key
profile analysis version
certainty
daily observation count
interest weights + trend
intent weights
keyword trends
tag trends
```

It intentionally excludes:

```text
cookies
passwords
Google email/account identifiers
profile display label
raw Home/Up Next rows
raw video URLs/history
subscribed-channel names/list
```

Local IDs live in:

```text
data/collector_identity.json
```

and are git-ignored.

## 6. Automatic sync agent

Run:

```bash
python scripts/community/collector_agent.py --endpoint https://COMMUNITY_SERVER
```

or set:

```text
YT_LIBRARY_COMMUNITY_ENDPOINT
YT_LIBRARY_COMMUNITY_TOKEN
```

The agent watches:

```text
data/profile_library/profile_*.json
```

Whenever a local collector updates a current profile, the agent automatically builds and uploads the sanitized summary.

It may optionally launch the local browser bridge:

```bash
python scripts/community/collector_agent.py --endpoint https://COMMUNITY_SERVER --launch-bridge
```

## 7. Community ingestion server

Run centrally:

```bash
set YT_LIBRARY_COMMUNITY_TOKEN=YOUR_RANDOM_SECRET
python scripts/community/community_server.py --host 0.0.0.0 --port 8770
```

For internet deployment, place it behind HTTPS/reverse proxy/firewall. Do not expose an unauthenticated HTTP service publicly.

Endpoint:

```text
POST /v1/profile
```

Every accepted submission replaces that profile's current central snapshot and rebuilds:

```text
data/community_reports/current.json
data/community_reports/current.html
```

## 8. Creator Community Intelligence

The central report is participant-balanced.

For each content lane it computes:

```text
community segment key
matched profile count
matched participant count
profile coverage
participant coverage
participant-balanced coverage
participant-balanced interest strength
trend breadth/momentum
core keywords
core tags
rising/emerging expansion keywords
top content intent
community opportunity score
```

Example interpretation:

```text
Community segment: science_technology::tutorial
Participants matched: 8 / 12
Profiles matched: 13 / 21
Core keys: AI video, creator workflow, automation
Core tags: ai video, creator tools
Expansion keys: agent workflow, AI voice
Fit band: strong
```

This means the lane is supported across the observed consenting community panel. It does **not** mean there is a known 67% chance of YouTube impressions/views.

## 9. Creator-facing wording

Prefer:

> This content direction matches 8/12 observed participants and 13/21 usable profiles, with rising support around these expansion keys.

Avoid:

> There is a 67% probability YouTube will recommend this video.

The project does not have access to YouTube's internal recommendation probabilities.

## 10. Architecture boundary

```text
Observed community data
→ creator opportunity
→ creator makes/publishes content organically
→ external real audience behaves naturally
```

Project collectors are measurement infrastructure. They are not a coordinated initial-view or engagement network.

## 11. Current browser behavior

Extension `0.6.1`:

```text
install/reload extension
→ passive collection defaults ON
→ visit youtube.com
→ content script schedules capture for the natural route
→ daily cap prevents excessive snapshots
```

Popup behavior:

```text
state shown as ACTIVE / PAUSED
button: Pause collection / Resume collection
```

No runtime opt-in checkbox is required after installation.

## 12. Next engineering slice

1. Validate auto-on browser capture with at least two independent participants/devices.
2. Validate that pause persists and resume can schedule capture on the current route without reopening YouTube.
3. Validate community ingestion with at least two independent participants/devices.
4. Build Android adapter against the same sanitized submission contract, starting only with read-only surfaces that can be accessed legitimately.
5. Move Creator Community Intelligence to the primary creator UI; individual profile reports become drill-down evidence.
