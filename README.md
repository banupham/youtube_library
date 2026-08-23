# YouTube Library

YouTube Library là hệ thống **community profile intelligence** cho creator. Dự án thu recommendation/affinity evidence và một số natural interaction events từ participant tự nguyện trên Chrome/Android, tạo longitudinal profiles, rồi tổng hợp theo participant thành content opportunities cho người sáng tạo.

## Kiến trúc gọn: 2 phía

```text
PARTICIPANT SIDE
Chrome Extension + Android App
        ↓
natural-use evidence
        ↓
CENTRAL SERVER :8770
collect / ingest
→ enrich / classify
→ temporal profile
→ participant-balanced aggregate
        ↓
CREATOR DASHBOARD
```

Collector chỉ quan sát hành vi người dùng thật; không tự click/play/like/comment/subscribe.

## Participant collectors

### Chrome `0.7.0`

Passive collector tự hoạt động khi participant dùng YouTube:

```text
Home → visible recommendation cards
Watch → video_open + Up Next
Subscriptions / Channels
Like / unlike / dislike / undislike
Comment submission event
```

Comment chỉ ghi **sự kiện đã gửi comment**, không ghi nội dung comment hay text người dùng gõ.

Chrome có Server URL / Project token / Participant ID trong popup và gửi trực tiếp tới Central Server. Browser tính `natural_interaction_v1` score trước khi gửi. Sau `/finalize`, central tự promote longitudinal Chrome profile thành sanitized community profile và rebuild Dashboard; không cần agent/server phụ.

### Android `0.3.0`

Android dùng AccessibilityService giới hạn vào:

```text
com.google.android.youtube
```

App quan sát bounded node tree và natural Accessibility events, tự queue/upload snapshot + interaction evidence theo Server URL / token / Participant ID / Profile slot.

Android chưa có fixture-tested video-card parser, nên video/channel/subscription metadata từ interaction có thể còn `unknown` cho tới khi parser được xác thực.

## Một Central Server

Chỉ chạy:

```bat
python scripts\community\community_server.py
```

Default:

```text
http://127.0.0.1:8770
```

Endpoints:

```text
GET  /                    Creator Dashboard
GET  /profile/<id>         Browser profile report
GET  /health               Server status
POST /collect              Chrome recommendation evidence
POST /finalize             Chrome longitudinal profile + community update
POST /v1/android/snapshot  Android raw Accessibility evidence
POST /v1/interaction       Natural interaction evidence
POST /v1/profile           Sanitized analyzed community profile
```

Không còn `home_bridge.py`, không còn server phụ `8765`.

Chrome analysis logic:

```text
scripts/community/browser_pipeline.py
```

Interaction storage/rollups:

```text
scripts/community/interaction_store.py
```

## Natural interaction evidence v1

```text
video_open       +0.25
like             +1.00
unlike           -1.00
dislike          -1.00
undislike        +1.00
comment_submit   +1.00
```

`like → unlike` và `dislike → undislike` là các delta đảo ngược nhau để tổng score không bị tích lũy sai khi người dùng đổi trạng thái.

Score model:

```text
natural_interaction_v1
```

Server lưu raw event theo ngày và tạo machine summaries:

```text
YYYY-MM-DD.jsonl
YYYY-MM-DD.json
rolling_7d.json
rolling_30d.json
```

Natural interaction là **lớp evidence riêng**. Hiện nó được hiển thị ở profile report nhưng chưa thay đổi Creator Opportunity ranking; cần dữ liệu thật và calibration trước khi đưa vào trọng số chiến lược.

Subscription status được giữ theo ba trạng thái:

```text
subscribed
not_subscribed
unknown
```

Chrome watch page có thể đọc trực tiếp nút Subscribe/Subscribed cho video đang mở. Up Next chỉ đánh dấu `subscribed` khi có evidence từ danh sách channel đã quan sát; nếu không đủ bằng chứng thì giữ `unknown`, không suy diễn thành non-subscribed.

## Creator output

Mở:

```text
http://127.0.0.1:8770/
```

Creator Dashboard giữ contract xuyên suốt:

```text
Participants / Profiles / Usable profiles
Top content opportunities
Participant coverage / profile coverage
Core keywords
Core tags
Expansion keywords
Top intent / format
Trend breadth: rising / stable / cooling
Recommended Anchor
Recommended Bridge
Controlled Expansion
Certainty / limitations
```

Các score/coverage là heuristic trên observed community panel, không phải xác suất YouTube recommendation/view.

## Data policy

`data/` là runtime workspace. Raw/intermediate/profile JSON chủ yếu để code đọc; Git chỉ giữ `data/README.md`.

Human-facing output ưu tiên dashboard/profile HTML. Raw JSON, Accessibility nodes và event JSONL không phải giao diện người dùng.

## Current status

```text
Chrome passive + interactions          implemented 0.7.0
Chrome configurable central sync       implemented
Chrome finalize → community dashboard  implemented
Central single process :8770           implemented 2.2
Daily / rolling 7d/30d interactions    implemented
Android collector source               implemented 0.3.0
Android snapshot + event auto sync      implemented
Android APK build                       source/workflow fixed; artifact still must be verified
Android node → normalized parser        pending real fixtures
Participant-balanced aggregator         implemented
Creator Dashboard                       implemented initial UI
Synthetic Viewer Robot                  sandbox only
```

## Principle

```text
REAL PARTICIPANT EVIDENCE
        ↓
PROFILE INTELLIGENCE
        ↓
COMMUNITY SUPPORT / CONTENT OPPORTUNITY
        ↓
CREATOR DECISION
        ↓
ORGANIC PUBLICATION + REAL AUDIENCE
```

Synthetic data không rewrite observed truth. Natural interaction evidence không được tự động biến thành YouTube ranking probability.

`PLAN.md` là checkpoint kỹ thuật hiện tại. `PROJECT_PLAN.md` giữ roadmap gốc/lịch sử thiết kế.
