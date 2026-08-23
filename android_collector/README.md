# Android YouTube Accessibility Collector

Version: `0.2.0`

## Goal

Allow a consenting Android participant to contribute natural-use YouTube recommendation evidence automatically.

```text
participant enables AccessibilityService once
        ↓
participant opens/uses YouTube normally
        ↓
service reads bounded AccessibilityNodeInfo tree
        ↓
local JSONL snapshot
        ↓
configured automatic upload
        ↓
central community_server.py
        ↓
raw Android ingest area
        ↓
future Android parser/profile engine
        ↓
sanitized community profile
        ↓
Creator Community Intelligence
```

The collector is read-only. It does not call `performAction()`, `dispatchGesture()`, media-control APIs, or input injection.

## Scope restriction

The AccessibilityService is restricted to:

```text
com.google.android.youtube
```

It listens only to:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
```

and requests `canRetrieveWindowContent=true` plus `FLAG_REPORT_VIEW_IDS`.

## Consent

The app shows an AccessibilityService disclosure and requires an affirmative button press before opening Android Accessibility Settings. After the participant enables the service, collection is automatic whenever YouTube is active. Pause/resume remains available in the app.

## Snapshot contract

Raw snapshot schema:

```text
schemas/android_accessibility_snapshot.v1.schema.json
```

Automatic server envelope schema:

```text
schemas/android_snapshot_ingest.v1.schema.json
```

Each accepted snapshot contains bounded evidence such as:

```text
captured_at
surface_guess + confidence/evidence
tree_signature
text/contentDescription/viewIdResourceName
className
selected/clickable/scrollable flags
child count
screen bounds
depth
```

Traversal is capped at 450 retained nodes / depth 18.

## Local storage first

Every accepted snapshot is written locally before network sync:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

It is also mirrored for ADB debugging to:

```text
/sdcard/Android/data/com.youtube.library.collector/files/
  youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

ADB and phone-side JSON export are now fallback/debug paths, not the normal production transport.

## Automatic server sync

Android `0.2.0` has app settings for:

```text
Server URL
Project token
Participant ID
Profile slot
Auto sync ON/OFF
Development HTTP override
```

The app generates a stable random `device_id` once.

A participant who uses multiple project devices/profiles should reuse the same project `participant_id` when those devices belong to the same real person. This prevents community aggregation from incorrectly counting one human as multiple independent participants.

Normal production configuration should use HTTPS. HTTP is exposed only as an explicit development/LAN override and sends data/token without transport encryption.

After settings are saved:

```text
new accepted snapshot
→ local snapshot
→ local pending queue
→ POST <server>/v1/android/snapshot
```

Pending queue:

```text
files/android_sync_queue/pending.jsonl
```

If network/server upload fails, the snapshot remains queued. The queue is retried on later captures, app launch, or AccessibilityService reconnect. Server-side `tree_signature` deduplication makes retries idempotent.

## Central server

The current central server module is:

```text
scripts/community/community_server.py
```

It now exposes two separate ingestion contracts:

```text
POST /v1/android/snapshot
    raw bounded Android Accessibility evidence
    → data/android_ingest/...

POST /v1/profile
    sanitized analyzed profile summary
    → data/community_profiles/...
    → rebuild Creator Community report
```

Raw Android snapshots do **not** directly change the Creator Dashboard. They first need the Android node parser/profile engine, then the resulting sanitized profile is submitted to `/v1/profile`.

Central aggregation remains:

```text
scripts/community/build_community_report.py
```

## Initial daily caps

```text
home            4/day
watch          24/day
subscriptions   4/day
shorts         12/day
search          8/day
unknown         6/day
```

These limits control raw collection volume, not participant weighting.

## ADB fallback / development bridge

PC tools remain available:

```text
scripts/android/android_bridge.py
scripts/android/android_bridge.cmd
```

Examples:

```bat
scripts\android\android_bridge.cmd devices
scripts\android\android_bridge.cmd status
scripts\android\android_bridge.cmd pull --today --inspect
scripts\android\android_bridge.cmd watch
```

Pulled raw snapshots go to `data/android_snapshots/` and are git-ignored.

## Current parser status

Surface detection remains provisional:

```text
home
watch
subscriptions
shorts
search
unknown
```

A strict video-card parser is intentionally deferred until real Accessibility node fixtures are available from multiple devices/YouTube versions.

The next data path is:

```text
central Android raw ingest / ADB fixtures
→ inspect stable node patterns
→ node-to-video-card parser
→ normalized Home / Watch / Subscriptions evidence
→ Android daily/temporal profile
→ community_profile_submission.v1
→ Creator Community Intelligence
```

## Account/profile switching

The collector does not scrape Google account names/emails. `profile_slot` is an explicit project label. If a participant switches multiple YouTube accounts inside one Android app without changing the project slot, evidence can mix.

## Build

GitHub Android build workflow:

```text
.github/workflows/android-apk.yml
```

A usable APK is considered available only when `:app:assembleDebug` succeeds and GitHub produces the artifact:

```text
youtube-library-collector-debug
```

Current build pins:

```text
JDK 17
Gradle 8.9
Android SDK 35
AGP 8.7.3
Kotlin 2.0.21
```

## Next Android slice

```text
successful APK build
→ configure central server auto sync
→ receive real Android snapshots automatically
→ node-to-video-card parser
→ Android temporal profile
→ sanitized /v1/profile submission
```
