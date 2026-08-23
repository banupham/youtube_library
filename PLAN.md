# /plan — YouTube Library canonical checkpoint

> Cập nhật: 2026-08-24
>
> Kiến trúc vận hành: **2 phía, 1 central process, 1 external port**.

# 1. Product goal

YouTube Library thu recommendation/affinity evidence thật và natural interaction evidence từ participant tự nguyện trên Chrome/Android, tạo profile theo thời gian, rồi tổng hợp thành Creator Community Intelligence.

Creator output giữ nguyên:

```text
Participants / Profiles / Usable profiles
Top content opportunities
Participant/profile coverage
Core keywords / tags
Expansion keys rising/emerging/revived
Top intent / format
Recommended Anchor
Recommended Bridge
Controlled Expansion
Certainty / limitations
```

Không gọi coverage/opportunity score là xác suất YouTube recommendation, impression hoặc view.

# 2. Canonical architecture

```text
PARTICIPANTS
Chrome + Android
      ↓
CENTRAL SERVER :8770
      ↓
recommendation ingest + interaction ingest
→ enrich → classify → temporal profile
→ participant-balanced aggregate
      ↓
CREATOR DASHBOARD
```

# 3. Participant side

## Chrome `0.7.0`

Path:

```text
browser_extension/youtube_home_collector/
```

Passive auto collection:

```text
Home visible videos
Watch-page Up Next
Subscriptions / Channels
video_open
like / unlike
dislike / undislike
comment_submit
```

Chrome popup now contains:

```text
Server URL
Project token
Participant ID
```

The same real participant should reuse the same Participant ID across their profiles/devices.

Chrome computes v1 interaction score before sending:

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

Comment content / typed text is not collected.

Subscription status:

```text
subscribed
not_subscribed
unknown
```

For the opened watch video Chrome can read Subscribe/Subscribed state directly. For recommendation cards, `subscribed` may be inferred from an observed subscribed-channel cache; absence without complete evidence remains `unknown`.

## Android `0.3.0`

Path:

```text
android_collector/
```

AccessibilityService is restricted to:

```text
com.google.android.youtube
```

Observed event types:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
TYPE_VIEW_CLICKED
```

Android queues and auto-syncs:

```text
POST /v1/android/snapshot
POST /v1/interaction
```

No `performAction()`, `dispatchGesture()`, player control or input injection.

Android interaction metadata is intentionally conservative until real node fixtures exist. video/channel/subscription fields can remain null/unknown.

# 4. Single central runtime

Only run:

```bat
python scripts\community\community_server.py
```

Default:

```text
http://127.0.0.1:8770
```

No `home_bridge.py`. No `8765`. No second HTTP process.

Central modules:

```text
scripts/community/community_server.py
scripts/community/browser_pipeline.py
scripts/community/interaction_store.py
scripts/community/build_community_report.py
```

Endpoints:

```text
GET  /                    Creator Dashboard
GET  /dashboard            Dashboard alias
GET  /profile/<id>         Browser profile HTML + interaction summary
GET  /health               JSON status
POST /collect              Chrome recommendation surface
POST /finalize             Chrome temporal profile update
POST /v1/android/snapshot  Android raw Accessibility ingest
POST /v1/interaction       Natural interaction ingest
POST /v1/profile           Sanitized analyzed profile
```

# 5. Interaction data contract

Schema:

```text
schemas/interaction_event.v1.schema.json
```

Central stores machine data:

```text
data/interaction_events/.../YYYY-MM-DD.jsonl
data/interaction_daily/.../YYYY-MM-DD.json
data/interaction_daily/.../rolling_7d.json
data/interaction_daily/.../rolling_30d.json
```

Raw interaction event is ground evidence. Score is a project heuristic and remains recalibratable.

Natural interaction summaries are attached to the longitudinal profile and shown in `/profile/<id>`, but **do not yet change Creator Opportunity ranking**.

# 6. Profile/community analysis

Recommendation evidence continues through:

```text
raw Home / Up Next / Subscriptions
→ YouTube metadata enrichment
→ content + intent classification
→ Today / 7d / 30d / Long-term
→ baseline / emerging / rising / stable / cooling / dormant / revived
→ longitudinal profile
→ participant-balanced community aggregate
→ Creator Dashboard
```

One participant with multiple profiles/devices still has one total community weight.

# 7. Android APK build

Previous APK pipeline was not confirmed successful. Build configuration has now been simplified to:

```text
JDK 17
Gradle 8.9
Android SDK 35
AGP 8.7.3
Kotlin 1.9.25
```

App version:

```text
0.3.0
```

Workflow:

```text
.github/workflows/android-apk.yml
```

Command:

```text
gradle -p android_collector --no-daemon --stacktrace --warning-mode all clean :app:assembleDebug
```

APK is not considered ready until GitHub produces artifact:

```text
youtube-library-collector-debug
```

# 8. Data policy

`data/` is runtime-only. Git keeps only `data/README.md`.

Human-facing:

```text
http://127.0.0.1:8770/
http://127.0.0.1:8770/profile/<id>
```

Raw/intermediate JSON/JSONL is for code, audit and debugging.

# 9. Current status

```text
Chrome passive recommendation collector      IMPLEMENTED 0.7.0
Chrome natural interaction collector         IMPLEMENTED v1
Chrome configurable central server           IMPLEMENTED
Chrome local daily interaction score         IMPLEMENTED

Central single process :8770                 IMPLEMENTED v2.1
Central interaction endpoint                 IMPLEMENTED
Daily / rolling 7d/30d interaction JSON      IMPLEMENTED
Interaction → Creator Opportunity weight     NOT ENABLED

Android Accessibility source                 IMPLEMENTED 0.3.0
Android snapshot auto-sync                   IMPLEMENTED
Android natural click event auto-sync        IMPLEMENTED, NEEDS REAL FIXTURE VALIDATION
Android APK workflow                         REVISED, ARTIFACT MUST BE VERIFIED
Android node → normalized video parser       PENDING REAL FIXTURES
Android exact subscription-state parser      PENDING REAL FIXTURES

Participant-balanced aggregator              IMPLEMENTED
Creator dashboard                            IMPLEMENTED initial UI
Synthetic Viewer Robot                       SANDBOX ONLY
```

# 10. Immediate sequence

```text
1. Verify Android Actions assembleDebug and download the APK artifact.
2. Install Android 0.3.0 and receive real auto-synced node + click fixtures.
3. Build fixture-tested Android node → Home/Watch/Subscriptions/video parser.
4. Add reliable Android video/channel/subscription state to interaction events.
5. Observe several days of interaction evidence and validate false-positive rate.
6. Only after validation decide how interaction scores should influence longitudinal interests/community opportunities.
```

# 11. Safety / interpretation boundary

- Collectors observe participant actions; they never create engagement.
- Comment text/content is never collected; only `comment_submit` event.
- Android Accessibility stays restricted to YouTube package.
- Multiple profiles from one participant do not count as independent humans.
- Interaction score is a transparent project heuristic, not YouTube ranking truth.
- Interaction score does not currently rewrite Creator Opportunity ranking.
- Synthetic viewer is not ground truth.

# 12. Continuation prompt

> Đọc `README.md` và `PLAN.md`. Chrome 0.7.0 và Android 0.3.0 now send recommendation/interaction evidence to the single Central Server :8770. InteractionStore writes daily + rolling 7d/30d JSON and does not store comment text. Next priority: verify Android APK artifact, then validate real Android Accessibility fixtures before building the strict node parser.
