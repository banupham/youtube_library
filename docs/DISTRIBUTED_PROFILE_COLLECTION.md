# Distributed Profile Collection Network

## Purpose

The project treats observed profile data as a **consenting community panel** rather than as a proxy for all YouTube users.

```text
PLATFORM COLLECTORS
Browser extension + Android Accessibility collector
        ↓
LOCAL PROFILE STATE
        ↓ sanitized summary only
COMMUNITY INGESTION + PARTICIPANT-BALANCED AGGREGATION
        ↓
Creator Community Intelligence
```

## 1. Participant vs profile/device slot

A participant is a real consenting project contributor. One participant may contribute multiple browser profiles or device-local collection slots.

```text
Participant A
├── Browser Profile A1
├── Browser Profile A2
└── Android Slot A3

Participant B
└── Browser Profile B1
```

The community engine does **not** count the example above as four independent people.

Each participant receives equal total community weight. Multiple profile/device slots divide that participant's weight according to profile quality/certainty.

Reports expose:

```text
participant_count
profile_count
usable_participant_count
usable_profile_count
```

## 2. Platform Collector contract

A collector may collect only disclosed, read-only evidence from the participant's platform.

Collectors must not automatically create engagement or alter recommendation state through synthetic actions.

Forbidden collector behavior:

```text
auto click
auto play
auto like/comment/subscribe
gesture/input injection solely for collection
```

## 3. Browser collector

Extension `0.6.1` defaults passive collection ON after installation for a participating profile.

```text
participant opens YouTube normally
→ Home opened naturally → passive Home snapshot
→ watch page opened naturally → passive Up Next snapshot
→ Subscriptions opened naturally → passive Subscriptions snapshot
```

Popup exposes Pause/Resume. Passive mode does not auto-navigate, auto-scroll or auto-play.

## 4. Android Accessibility collector

Android collector foundation lives in:

```text
android_collector/
```

The participant first sees a prominent in-app disclosure, then explicitly opens Android Accessibility Settings and enables the service.

After the service is enabled:

```text
participant opens native YouTube normally
        ↓
AccessibilityService receives YouTube UI events
        ↓
rootInActiveWindow / AccessibilityNodeInfo tree
        ↓
bounded local snapshot
```

The service is restricted both statically and at runtime to:

```text
com.google.android.youtube
```

Service configuration:

```text
android_collector/app/src/main/res/xml/accessibility_service_config.xml
```

It declares:

```text
canRetrieveWindowContent=true
packageNames=com.google.android.youtube
FLAG_REPORT_VIEW_IDS
```

and listens to:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
```

The Android collector does **not** call Accessibility interaction APIs such as `performAction()` or `dispatchGesture()`.

### 4.1 Android v0.1 raw snapshot

Schema:

```text
schemas/android_accessibility_snapshot.v1.schema.json
```

Each bounded node may contain:

```text
text
contentDescription
viewIdResourceName
className
selected/clickable/scrollable
child count
bounds
depth
```

Traversal/string limits prevent storing an unbounded UI dump.

Raw snapshots stay in app-internal storage:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

Android v0.1 does not request `INTERNET` permission and does not upload raw node snapshots.

### 4.2 Surface detection

Initial provisional surface labels:

```text
home
watch
subscriptions
shorts
search
unknown
```

The first detector is intentionally heuristic. YouTube native accessibility hierarchies can change across app versions/locales and do not necessarily map one-to-one to Android Views.

Therefore the parser must be developed from real participant-consented fixtures:

```text
real Home/Watch/Subscriptions/Shorts/Search node snapshots
→ inspect stable patterns
→ fixture tests
→ node-to-video-card parser
→ normalized surface evidence
```

Local inspector:

```bash
python scripts/android/inspect_accessibility_snapshots.py snapshots.jsonl
```

Use `--show-text` only locally because text/content descriptions are participant-specific evidence.

### 4.3 Android account-switch limitation

Android v0.1 deliberately does not scrape Google account email/name to identify YouTube account switching.

One app installation currently represents one Android collection slot. If a participant mixes multiple YouTube accounts in the same app, evidence may mix. A later version should use an explicit non-sensitive local slot selector instead of scraping account identity.

### 4.4 Accessibility policy boundary

The collector is not a disability-support accessibility tool (`isAccessibilityTool=false`). If distributed through Google Play, it requires the appropriate Accessibility declaration, prominent disclosure/affirmative consent, Privacy Policy and Data Safety disclosure for the actual shipped behavior.

## 5. Local profile engine

Browser already has the mature local pipeline:

```text
Home + Up Next + Subscriptions
→ classifier/API enrichment
→ daily observation
→ Today / 7d / 30d / Long-term
→ trend states
→ current longitudinal profile
```

Android will reach the same logical output after its node-to-video parser is validated.

The goal is not for the community server to understand platform-specific raw UI trees. Platform-specific collectors should converge into the same profile semantics before community upload.

## 6. Sanitized community submission

Canonical schema:

```text
schemas/community_profile_submission.v1.schema.json
```

The sanitized payload contains only fields needed for community analysis:

```text
random participant_id
random device_id
stable profile_key
analysis version
certainty
daily observation count
interest weights + trends
intent weights
keyword trends
tag trends
```

It excludes:

```text
cookies/passwords
Google email/account identifiers
raw browser recommendation rows
raw Android Accessibility node tree
raw browsing/watch history
subscribed-channel names/list
```

## 7. Browser automatic sync

Current desktop agent:

```bash
python scripts/community/collector_agent.py --endpoint https://COMMUNITY_SERVER
```

It watches browser local longitudinal profiles and uploads only sanitized summaries.

Android network sync will be added only after an Android local profile summary exists; raw Accessibility snapshots remain local.

## 8. Community ingestion server

Central server:

```bash
python scripts/community/community_server.py --host 0.0.0.0 --port 8770
```

Endpoint:

```text
POST /v1/profile
```

Use HTTPS/reverse proxy/firewall/authentication for internet deployment.

Accepted submissions rebuild:

```text
data/community_reports/current.json
data/community_reports/current.html
```

## 9. Creator Community Intelligence

The central report is participant-balanced.

For each content lane it computes:

```text
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

Example:

```text
Community segment: science_technology::tutorial
Participants matched: 8 / 12
Profiles matched: 13 / 21
Core keys: AI video, creator workflow, automation
Expansion keys: agent workflow, AI voice
Fit band: strong
```

This is evidence from the observed community panel, not a known probability of YouTube impressions/views.

## 10. Architecture boundary

```text
Observed community data
→ creator opportunity
→ creator publishes organically
→ external real audience behaves naturally
```

Collectors are measurement infrastructure, not a coordinated initial-view or engagement network.

## 11. Next engineering slice

1. Build/install Android collector v0.1 on test devices.
2. Gather participant-consented node fixtures from native YouTube Home/Watch/Subscriptions/Shorts/Search.
3. Build fixture-tested node-to-video-card parser.
4. Produce Android daily/temporal profile semantics compatible with browser output.
5. Emit `community_profile_submission.v1` on Android and add sanitized sync.
6. Validate mixed Browser + Android community aggregation across at least two independent participants.
7. Make Creator Community Intelligence the primary creator UI.
