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

v1 writes JSONL only to app-internal storage:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

Raw node trees are **not** sent to the community server in v1.

For parser validation the participant can explicitly open the collector app and press:

```text
Xuất snapshot JSONL hôm nay
```

Android then opens the system document picker. Nothing is exported unless the participant chooses a destination.

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
4. Use **Xuất snapshot JSONL hôm nay** to export a small participant-approved fixture.
5. Inspect it locally with `scripts/android/inspect_accessibility_snapshots.py`.
6. Identify stable node patterns for video title/channel/metadata/recommendation sections.
7. Add fixture-based parser tests.
8. Only then map Android evidence into the same logical surfaces used by the browser profile engine.

## Current limitation: account/profile switching

Android v1 intentionally does not read Google account names/emails to identify in-app YouTube account switches. Therefore one app installation currently represents one Android collection slot.

If a participant switches between multiple YouTube accounts in the same Android app, snapshots may mix. A later version should add an explicit non-sensitive local profile slot selector rather than scraping account identity.

## Build

Open `android_collector/` in Android Studio, sync Gradle and install the `app` module on a test device.

The Gradle versions are repository pins for the prototype and may be updated when the project adopts a formal Android CI matrix. The current repository CI validates schemas/XML/guardrails but does not yet perform a full Android SDK build.

## Next Android slice

```text
real node-tree fixtures
→ node-to-video-card parser
→ Android daily surface profile
→ Android temporal profile
→ community_profile_submission.v1
→ automatic sanitized community sync
```
