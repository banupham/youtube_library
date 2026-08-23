# Android YouTube Accessibility Collector

Version: `0.3.0`

## Goal

Allow a consenting Android participant to contribute natural-use YouTube recommendation and interaction evidence automatically.

```text
participant enables AccessibilityService once
        ↓
participant uses YouTube normally
        ↓
bounded AccessibilityNodeInfo snapshots
+ natural click/watch transition events
        ↓
local queue
        ↓
configured automatic upload
        ↓
central community_server.py :8770
```

The collector observes events only. It does not call `performAction()`, `dispatchGesture()`, media-control APIs, or input injection.

## Scope

AccessibilityService is restricted to:

```text
com.google.android.youtube
```

It listens to:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
TYPE_VIEW_CLICKED
```

and requests `canRetrieveWindowContent=true` plus `FLAG_REPORT_VIEW_IDS`.

## What is collected

Snapshot evidence remains bounded to 450 retained nodes / depth 18 and includes visible Accessibility text/description/view-id evidence needed for future Home/Watch/Subscriptions parsing.

Natural interaction v1 additionally observes supported events:

```text
video_open       +0.25
like             +1.00
unlike           -1.00
dislike          -1.00
undislike         0.00
comment_submit   +1.00
```

Score model:

```text
natural_interaction_v1
```

`comment_submit` means only that a comment submission action was observed. **Comment text, typed text and comment body are not uploaded or stored.** Interaction detection is heuristic until validated against real YouTube Accessibility fixtures.

Android does not yet have a stable node-to-video parser, so interaction video ID/title/channel and subscribed/non-subscribed state can remain `null/unknown` until fixture-tested parsing is implemented.

## Settings / automatic sync

The app has:

```text
Server URL
Project token
Participant ID
Profile slot
Auto sync ON/OFF
Development HTTP override
```

A stable random device ID is created once. The same real participant should reuse the same Participant ID across their browser profiles and Android devices.

Normal production configuration should use HTTPS. HTTP is an explicit development/LAN override.

Two local retry queues are maintained:

```text
files/android_sync_queue/pending_snapshots.jsonl
files/android_sync_queue/pending_interactions.jsonl
```

Endpoints:

```text
POST <server>/v1/android/snapshot
POST <server>/v1/interaction
```

Raw snapshot evidence and interaction evidence are separate. Interaction events do not currently change Creator Opportunity ranking; they are retained as an additional longitudinal profile signal for later calibration.

## Local snapshot storage

Canonical private snapshot copy:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

ADB debug mirror:

```text
/sdcard/Android/data/com.youtube.library.collector/files/
  youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

ADB/CMD and phone-side export are debug/fallback paths, not normal transport.

## Central storage

Central server remains one process / one port:

```bat
python scripts\community\community_server.py
```

Default:

```text
http://127.0.0.1:8770
```

Android raw node evidence:

```text
data/android_ingest/...
```

Interaction raw/daily/rolling evidence:

```text
data/interaction_events/.../YYYY-MM-DD.jsonl
data/interaction_daily/.../YYYY-MM-DD.json
data/interaction_daily/.../rolling_7d.json
data/interaction_daily/.../rolling_30d.json
```

## Initial snapshot caps

```text
home            4/day
watch          24/day
subscriptions   4/day
shorts         12/day
search          8/day
unknown         6/day
```

These caps control snapshot volume, not community participant weighting.

## Parser status

Surface detection remains provisional:

```text
home
watch
subscriptions
shorts
search
unknown
```

A strict video-card parser remains intentionally deferred until real Accessibility fixtures from multiple devices/YouTube versions are available. This avoids turning unstable node assumptions into profile truth.

## Build

GitHub workflow:

```text
.github/workflows/android-apk.yml
```

Current build pins:

```text
JDK 17
Gradle 8.9
Android SDK 35
AGP 8.7.3
Kotlin 1.9.25
```

The app is considered installable only when `:app:assembleDebug` succeeds and GitHub produces:

```text
youtube-library-collector-debug
```

The source/workflow have been revised for the previous build failure, but do not call the APK ready until that artifact is confirmed.
