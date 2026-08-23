# Android YouTube Accessibility Collector

Version: `0.1.0` (collector foundation)

## Goal

Allow a consenting Android participant to contribute natural-use YouTube recommendation evidence without requiring manual collection each time.

```text
participant enables AccessibilityService once
        ↓
participant opens/uses YouTube normally
        ↓
service receives YouTube accessibility events
        ↓
read rootInActiveWindow / AccessibilityNodeInfo tree
        ↓
bounded local snapshot
        ↓
future Android parser/profile engine
        ↓ sanitized summary
community server
```

The collector is read-only. It does not call `performAction()`, `dispatchGesture()`, media-control APIs, or input injection.

## Scope restriction

The service is statically restricted to:

```text
com.google.android.youtube
```

in `res/xml/accessibility_service_config.xml` and checks the package again at runtime.

It listens only to:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
```

and requests `canRetrieveWindowContent=true` plus `FLAG_REPORT_VIEW_IDS`.

## Consent / Play policy

This app is not declared as an accessibility tool for disability support. Before opening Android Accessibility Settings, the app shows a prominent disclosure and requires an affirmative button press. The service also refuses to collect until that local disclosure flag has been accepted.

After the participant enables the service, collection is automatic whenever YouTube is active. The participant can pause/resume collection from the app.

## Snapshot contract

Schema:

```text
schemas/android_accessibility_snapshot.v1.schema.json
```

Each snapshot contains:

```text
captured_at
source_package = com.google.android.youtube
event_type
surface_guess
surface confidence/evidence
tree_signature
bounded evidence nodes
```

Each evidence node may contain:

```text
text
contentDescription
viewIdResourceName
className
selected/clickable/scrollable flags
child count
screen bounds
depth
```

Strings are length-limited and the traversal is capped at 450 retained nodes / depth 18.

## Local-first data handling

v1 keeps a canonical private JSONL copy in app-internal storage:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

For PC/ADB retrieval, the same accepted snapshot line is mirrored to app-specific external storage:

```text
/sdcard/Android/data/com.youtube.library.collector/files/
  youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

This is not the public Downloads directory and raw node trees are **not** sent to the community server in v1.

The participant can still use the in-app fallback:

```text
Xuất snapshot JSONL hôm nay
```

but normal development/testing should use the ADB CMD bridge below so no phone-side file copying is required.

Daily caps + tree-signature deduplication reduce repeated captures caused by Android UI event noise.

Initial caps:

```text
home            4/day
watch          24/day
subscriptions   4/day
shorts         12/day
search          8/day
unknown         6/day
```

These are collector engineering defaults, not behavioral weights. Community aggregation remains participant-balanced.

## ADB / CMD bridge

PC tool:

```text
scripts/android/android_bridge.py
scripts/android/android_bridge.cmd
```

Prerequisite: Android SDK Platform-Tools (`adb`) must be in `PATH`, or `ANDROID_HOME` / `ANDROID_SDK_ROOT` must point to the SDK.

### USB workflow

Enable Developer options + USB debugging on the test device, authorize the PC once, then:

```bat
scripts\android\android_bridge.cmd devices
scripts\android\android_bridge.cmd status
scripts\android\android_bridge.cmd pull --today
```

Pulled snapshots go to:

```text
data/android_snapshots/<device-serial>/YYYY-MM-DD.jsonl
```

and are git-ignored.

To automatically keep the PC copy current while the participant uses YouTube:

```bat
scripts\android\android_bridge.cmd watch
```

Default poll interval is 15 seconds. The bridge compares remote/local file size and only pulls when today's JSONL changes.

Optional immediate inspection:

```bat
scripts\android\android_bridge.cmd pull --today --inspect
scripts\android\android_bridge.cmd pull --today --inspect --show-text
```

### Multiple devices

```bat
scripts\android\android_bridge.cmd devices
scripts\android\android_bridge.cmd --serial SERIAL status
scripts\android\android_bridge.cmd --serial SERIAL watch
```

### Wireless debugging

Android 11+ can pair ADB over Wi-Fi from Developer options → Wireless debugging.

```bat
scripts\android\android_bridge.cmd pair 192.168.1.50:PAIRING_PORT
scripts\android\android_bridge.cmd connect 192.168.1.50:ADB_PORT
scripts\android\android_bridge.cmd status
scripts\android\android_bridge.cmd watch
```

The pairing port and normal ADB connection port may be different. Wireless debugging should only be enabled on trusted networks/devices.

### Retrieval fallback

The preferred transport is the app-specific external mirror. If that path cannot be pulled, `android_bridge.py` tries `adb exec-out run-as ...` against the canonical internal file. `run-as` normally works only for debuggable builds, so it is a development fallback rather than the primary design.

## Surface detection

`SurfaceDetector.kt` currently provides a provisional guess:

```text
home
watch
subscriptions
shorts
search
unknown
```

using selected navigation labels, accessibility text/content descriptions and view IDs when available.

This is deliberately marked provisional. Native YouTube accessibility trees can change between app versions/locales and may not map 1:1 to Android Views.

### Validation sequence

Before implementing a strict video-card parser:

1. Install the app on at least 2 Android devices / YouTube versions.
2. Enable the AccessibilityService.
3. Naturally visit Home, Watch, Subscriptions, Shorts and Search.
4. Run `scripts\android\android_bridge.cmd watch` on the PC.
5. Inspect pulled snapshots locally with `scripts/android/inspect_accessibility_snapshots.py` or `pull --inspect --show-text`.
6. Identify stable node patterns for video title/channel/metadata/recommendation sections.
7. Add fixture-based parser tests.
8. Only then map Android evidence into the same logical surfaces used by the browser profile engine.

## Current limitation: account/profile switching

Android v1 intentionally does not read Google account names/emails to identify in-app YouTube account switches. Therefore one app installation currently represents one Android collection slot.

If a participant switches between multiple YouTube accounts in the same Android app, snapshots may mix. A later version should add an explicit non-sensitive local profile slot selector rather than scraping account identity.

## Build

Open `android_collector/` in Android Studio, sync Gradle and install the `app` module on a test device.

The Gradle versions are repository pins for the prototype and may be updated when the project adopts a formal Android CI matrix. The current repository CI validates schemas/XML/guardrails/Python bridge syntax but does not yet perform a full Android SDK build.

## Next Android slice

```text
ADB-collected real node-tree fixtures
→ node-to-video-card parser
→ Android daily surface profile
→ Android temporal profile
→ community_profile_submission.v1
→ automatic sanitized community sync
```
