# Distributed Profile Collection Network

## Purpose

The project treats observed profile data as a **consenting community panel** rather than as a proxy for all YouTube users.

```text
PLATFORM COLLECTORS
Browser extension + Android Accessibility collector
        ↓
PLATFORM-SPECIFIC INGEST / LOCAL STATE
        ↓
NORMALIZED PROFILE SEMANTICS
        ↓
SANITIZED COMMUNITY PROFILE
        ↓
PARTICIPANT-BALANCED AGGREGATION
        ↓
Creator Community Intelligence
```

## 1. Participant vs profile/device slot

A participant is one real project contributor. One participant may contribute multiple browser profiles or Android device/profile slots.

```text
Participant A
├── Browser Profile A1
├── Browser Profile A2
└── Android Slot A3

Participant B
└── Browser Profile B1
```

The community engine does not count that example as four independent people. Each participant receives the same total community weight; multiple slots divide that participant's weight according to profile quality/certainty.

## 2. Collector boundary

Collectors may collect disclosed read-only recommendation/affinity evidence from the participant's platform.

They must not automatically create engagement or modify YouTube state through synthetic actions.

Forbidden collector behavior includes:

```text
auto click
auto play
auto like/comment/subscribe
gesture/input injection solely for collection
```

## 3. Browser collector

Extension `0.6.1` defaults passive collection ON after installation for a participating profile.

```text
Home opened naturally → passive Home snapshot
watch page opened naturally → passive Up Next snapshot
Subscriptions opened naturally → passive Subscriptions snapshot
```

Browser evidence is normalized locally and the desktop community agent uploads sanitized longitudinal profile summaries.

## 4. Android Accessibility collector

Android collector `0.2.0` lives in:

```text
android_collector/
```

After the participant accepts the disclosure and enables AccessibilityService once:

```text
participant uses native YouTube normally
        ↓
AccessibilityService receives YouTube UI events
        ↓
rootInActiveWindow / AccessibilityNodeInfo tree
        ↓
bounded raw snapshot
```

The service is statically/runtime restricted to:

```text
com.google.android.youtube
```

It uses read-only node retrieval and does not call Accessibility interaction APIs such as `performAction()` or `dispatchGesture()`.

### 4.1 Android raw snapshot

Schema:

```text
schemas/android_accessibility_snapshot.v1.schema.json
```

Traversal is bounded to 450 retained nodes / depth 18 with string limits.

Every accepted snapshot is stored locally first:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

### 4.2 Android automatic server sync

Android `0.2.0` adds configured automatic upload.

App settings:

```text
Server URL
Project token
Participant ID
Profile slot
Auto sync ON/OFF
Development HTTP override
```

The app generates a stable random `device_id`.

Automatic transport:

```text
accepted snapshot
→ local JSONL
→ local pending queue
→ POST <server>/v1/android/snapshot
```

Envelope schema:

```text
schemas/android_snapshot_ingest.v1.schema.json
```

If upload fails, the snapshot stays in the local queue and is retried on later captures/app/service reconnect. Server `tree_signature` deduplication makes retries safe.

Normal deployment should use HTTPS. HTTP is available only as an explicit development override.

### 4.3 ADB is fallback/debug

ADB remains useful for parser development:

```text
scripts/android/android_bridge.py
scripts/android/android_bridge.cmd
```

It is no longer the normal data transport once auto-sync is configured.

## 5. Central server architecture

The current central API server is:

```text
scripts/community/community_server.py
```

It now has two separate evidence contracts.

### Raw Android ingest

```text
POST /v1/android/snapshot
```

Stores bounded Android envelopes under:

```text
data/android_ingest/
```

Raw Android Accessibility data does **not** directly affect creator-facing aggregation.

### Sanitized profile ingest

```text
POST /v1/profile
```

Stores analyzed profile summaries under:

```text
data/community_profiles/
```

and triggers the community report builder:

```text
scripts/community/build_community_report.py
```

Outputs:

```text
data/community_reports/current.json
data/community_reports/current.html
```

Thus the central system is conceptually:

```text
community_server.py
        ├── raw platform ingest
        └── sanitized profile ingest
                 ↓
        build_community_report.py
                 ↓
        Creator Community Intelligence
```

## 6. Android parser boundary

Raw node trees cannot be treated as profile truth directly.

The Android path must become:

```text
raw node snapshot
→ node-to-video-card parser
→ normalized Home / Watch / Subscriptions evidence
→ classifier / temporal profile
→ community_profile_submission.v1
→ POST /v1/profile
```

Only the final sanitized profile participates in community coverage/opportunity calculations.

## 7. Participant identity

`participant_id` is a project identity, not a Google account identifier.

If the same real person contributes Browser + Android or multiple devices, those installations should use the same project participant ID so the participant-balanced aggregator does not count one person several times.

`device_id` is installation-specific and Android generates it locally.

The collector does not need Google email/account identity.

## 8. Creator Community Intelligence

The central report remains participant-balanced and returns fields such as:

```text
matched profile count
matched participant count
profile coverage
participant coverage
participant-balanced interest strength
trend breadth/momentum
core keywords
core tags
rising/emerging expansion keywords
top content intent
community opportunity score
```

These describe support in the observed community panel, not a known probability of YouTube impressions/views.

## 9. Deployment

Start central server:

```bash
set YT_LIBRARY_COMMUNITY_TOKEN=YOUR_RANDOM_SECRET
python scripts/community/community_server.py --host 0.0.0.0 --port 8770
```

For Internet deployment, place it behind HTTPS/reverse proxy/firewall. The same Bearer token protects `/v1/profile` and `/v1/android/snapshot` when `YT_LIBRARY_COMMUNITY_TOKEN` is set.

## 10. Next engineering slice

1. Get Android APK workflow green and install `0.2.0`.
2. Configure server URL/token/participant/profile slot in app.
3. Confirm Android snapshots arrive automatically under `data/android_ingest/`.
4. Build fixture-tested node-to-video-card parser using central/raw or ADB fixtures.
5. Produce Android daily/temporal profile output.
6. Submit Android sanitized profile to `/v1/profile` automatically.
7. Validate mixed Browser + Android participant-balanced aggregation.
8. Make Creator Community Intelligence the primary creator UI.
