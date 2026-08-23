# YouTube Library

YouTube Library là hệ thống **community profile intelligence** cho creator. Dự án thu recommendation/affinity evidence từ những người tham gia tự nguyện trên Chrome và Android, phân tích thành longitudinal profiles, rồi tổng hợp theo participant để trả ra content opportunities cho người sáng tạo.

Mục tiêu sản phẩm không phải dự đoán chắc chắn view hay mô phỏng thuật toán YouTube. Mục tiêu là trả lời:

```text
Cộng đồng hiện có bao nhiêu participant/profile hữu dụng?
Những content lane nào đang xuất hiện rộng trong cộng đồng?
Core keywords/tags là gì?
Keys mở rộng nào đang rising/emerging?
Nên giữ anchor, đi bridge hay controlled expansion?
Mức support/certainty và limitation hiện tại là gì?
```

## Kiến trúc: 2 phần chính

```text
┌──────────────────────────────────────┐
│ 1. PHÍA NGƯỜI THAM GIA CỘNG ĐỒNG    │
│                                      │
│ Chrome Extension     Android App     │
│ passive DOM          Accessibility   │
│ Home/Up Next/Subs    Node Tree       │
│        │                  │          │
│        └────── upload ────┘          │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ 2. TRUNG TÂM PHÂN TÍCH              │
│                                      │
│ ingest → normalize → enrich          │
│ → classify → temporal profile        │
│ → participant-balanced aggregate     │
│ → creator intelligence               │
└──────────────────┬───────────────────┘
                   │
                   ▼
          Creator Dashboard
```

### 1. Phía người tham gia cộng đồng

#### Chrome

```text
browser_extension/youtube_home_collector/
```

Extension `0.6.1` auto-on khi participant truy cập YouTube và chỉ quan sát natural navigation:

```text
Home
Watch-page Up Next
Subscriptions / Channels
```

Không auto-click/play/scroll/like/comment/subscribe.

**Trạng thái hiện tại:** Chrome vẫn gửi snapshot tới local Python bridge tại `127.0.0.1:8765`, sau đó local profile engine mới sync summary lên central. Đây là transitional architecture.

**Trạng thái đích:** extension cấu hình server giống Android và push raw browser evidence trực tiếp lên central; participant không cần Python/terminal.

#### Android

```text
android_collector/
```

Android collector `0.2.0` dùng `AccessibilityService`, giới hạn vào package:

```text
com.google.android.youtube
```

Participant bật quyền trợ năng một lần. Sau đó khi YouTube mở, app đọc bounded `AccessibilityNodeInfo` tree, lưu local và có thể tự upload tới central server theo cấu hình:

```text
Server URL
Project token
Participant ID
Profile slot
Auto sync ON/OFF
```

App không gọi `performAction()`, `dispatchGesture()` hoặc input injection.

ADB/CMD bridge vẫn giữ để debug/fixture, không phải transport sản phẩm chính.

### 2. Trung tâm phân tích

Ingestion server:

```text
scripts/community/community_server.py
```

Endpoints hiện tại:

```text
GET  /health
POST /v1/android/snapshot   # raw Android evidence, lưu riêng
POST /v1/profile            # analyzed/sanitized profile summary
```

Central analysis dùng các module:

```text
scripts/community/          # ingest + participant-balanced aggregate
scripts/classification/     # content classification
scripts/enrichment/         # YouTube metadata enrichment
scripts/profile/            # session + longitudinal profile
scripts/homepage/           # browser bridge/legacy transition
scripts/android/            # Android debug/fixture tools
taxonomy/                   # category/relationship rules
schemas/                    # transport/state contracts
```

Target central pipeline:

```text
raw platform evidence
→ normalized surface evidence
→ metadata enrichment
→ content/intent classification
→ per-profile daily/longitudinal state
→ cross-profile participant-balanced aggregation
→ creator report
```

Một participant có nhiều profile/device slot vẫn chỉ có một tổng community weight; nhiều profile chia nhau trọng số của participant đó.

## Creator output

Primary human-facing output:

```text
data/community_reports/current.html
```

Machine/API representation:

```text
data/community_reports/current.json
```

Dashboard cần trả:

```text
Participants / Profiles / Usable profiles
Top content opportunities
Participant coverage / profile coverage
Core keywords
Core tags
Expansion keywords
Top intent/format
Trend breadth: rising / stable / cooling
Recommended anchor
Recommended bridge
Controlled expansion
Certainty / limitations
```

Các `community_opportunity_score`, coverage và fit band là project heuristics trên observed community panel; không gọi là xác suất YouTube recommendation/view.

## Data policy

`data/` là runtime workspace. Raw/intermediate/profile JSON chủ yếu để **code đọc**, không phải người dùng đọc. Git chỉ giữ `data/README.md`; các thư mục runtime được code tự tạo khi cần.

Xem `data/README.md` để biết các lớp raw/intermediate/profile/output.

## Trạng thái hiện tại

```text
Browser passive collector          implemented, local bridge transitional
Android Accessibility collector   source 0.2.0 implemented, APK build must be verified by Android workflow
Central community server          v1.1 implemented
Participant-balanced aggregator   implemented
Longitudinal browser profiles     implemented
Android node → video parser       pending real fixtures/validation
Chrome direct → central upload    pending refactor
Creator Community Dashboard       initial HTML/JSON implemented
Synthetic Viewer Robot            sandbox only, not ground truth
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

Collector không tạo engagement. Synthetic data không rewrite observed truth. Creator output là audience-fit/community-support evidence, không phải lời hứa về view.

`PLAN.md` là checkpoint kỹ thuật hiện tại. `PROJECT_PLAN.md` giữ roadmap gốc/lịch sử thiết kế.
