# YouTube Library

YouTube Library là hệ thống **community profile intelligence** cho creator. Dự án thu recommendation/affinity evidence từ những người tham gia tự nguyện trên Chrome và Android, phân tích thành longitudinal profiles, rồi tổng hợp theo participant để trả ra content opportunities cho người sáng tạo.

## Kiến trúc gọn: 2 phía

```text
PARTICIPANT SIDE
Chrome Extension + Android App
        ↓
read-only natural-use evidence
        ↓
CENTRAL SERVER :8770
collect / ingest
→ enrich / classify
→ temporal profile
→ participant-balanced aggregate
        ↓
CREATOR DASHBOARD
```

### Phía người tham gia

Chrome extension tự quan sát Home, natural Watch-page Up Next và Subscriptions khi participant dùng YouTube. Android app dùng AccessibilityService giới hạn vào `com.google.android.youtube` và tự upload snapshot theo cấu hình.

Collector không auto-click/play/like/comment/subscribe.

### Trung tâm phân tích

Chỉ chạy **một process, một port**:

```bat
python scripts\community\community_server.py
```

Mặc định:

```text
http://127.0.0.1:8770
```

Các endpoint chính:

```text
GET  /                    Creator Dashboard
GET  /profile/<id>         Browser profile report
GET  /health               Server status
POST /collect              Chrome surface evidence
POST /finalize             Build/update Chrome longitudinal profile
POST /v1/android/snapshot  Android raw evidence
POST /v1/profile           Sanitized analyzed profile for community aggregate
```

Không còn `home_bridge.py`, không còn server phụ `8765`.

Logic Chrome chạy trực tiếp trong:

```text
scripts/community/browser_pipeline.py
```

Central server:

```text
scripts/community/community_server.py
```

## Giao diện kết quả

Mở:

```text
http://127.0.0.1:8770/
```

để xem Creator Community Dashboard.

Manual collect trên Chrome sẽ tự mở:

```text
http://127.0.0.1:8770/profile/<profile-id>
```

để xem profile report trên trình duyệt.

Creator Dashboard cần trả:

```text
Participants / Profiles / Usable profiles
Top content opportunities
Participant coverage / profile coverage
Core keywords
Core tags
Expansion keywords
Top intent / format
Trend breadth: rising / stable / cooling
Recommended anchor
Recommended bridge
Controlled expansion
Certainty / limitations
```

Các score là heuristic trên observed community panel, không phải xác suất YouTube recommendation/view.

## Data policy

`data/` là runtime workspace. Raw/intermediate/profile JSON chủ yếu để **code đọc**, không phải người dùng đọc. Git chỉ giữ `data/README.md`; code tự tạo runtime directories khi cần.

Human-facing output ưu tiên dashboard HTML. JSON dùng cho code/API/debug.

## Trạng thái hiện tại

```text
Chrome passive collector              implemented 0.6.2
Chrome → single central :8770         implemented
Chrome in-process profile pipeline    implemented
Android Accessibility collector       source 0.2.0 implemented
Android APK build                     cần tiếp tục fix/verify GitHub Actions
Android raw central ingest            implemented
Android node → normalized parser      pending real fixtures
Participant-balanced aggregator       implemented
Creator Dashboard                     initial HTML/JSON implemented + served at /
Synthetic Viewer Robot                sandbox only
```

## Nguyên tắc xuyên suốt

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

Collector không tạo engagement. Synthetic data không rewrite observed truth. Creator output là community-support/audience-fit evidence, không phải lời hứa về view.

`PLAN.md` là checkpoint kỹ thuật hiện tại. `PROJECT_PLAN.md` giữ roadmap gốc/lịch sử thiết kế.
