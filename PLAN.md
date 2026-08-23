# /plan — YouTube Library canonical checkpoint

> Cập nhật: 2026-08-23
>
> `README.md` là entry point. `PROJECT_PLAN.md` giữ roadmap gốc/lịch sử thiết kế. File này chỉ giữ trạng thái kỹ thuật hiện tại và next steps.

# 1. Mục tiêu sản phẩm

YouTube Library là hệ thống **community profile intelligence** cho creator.

Nguồn evidence chính là recommendation/affinity state thật từ những participant tự nguyện sử dụng YouTube tự nhiên trên Chrome hoặc Android.

Kết quả cuối cho creator phải trả lời:

```text
Có bao nhiêu participants / profiles đang được theo dõi?
Bao nhiêu profile đủ evidence để dùng?
Content lane nào có support rộng nhất trong community panel?
Core keys / keywords / tags là gì?
Keys mở rộng nào đang rising/emerging/revived?
Intent/format nào phù hợp?
Nên giữ anchor, đi bridge hay controlled expansion?
Mức certainty và limitation hiện tại là gì?
```

Không gọi coverage/opportunity score là xác suất YouTube recommendation, impression hoặc view.

---

# 2. Kiến trúc chỉ còn 2 phần chính

```text
PARTICIPANT SIDE
Chrome Extension + Android App
        ↓
read-only natural-use evidence
        ↓
CENTRAL ANALYSIS
Ingest → Normalize → Enrich → Classify
→ Temporal Profile → Community Aggregate
        ↓
CREATOR DASHBOARD
```

## 2A. Phía người tham gia cộng đồng

Participant side phải càng nhẹ càng tốt:

```text
cài collector
→ cấu hình identity/server một lần nếu cần
→ dùng YouTube bình thường
→ collector tự quan sát + upload
```

Participant không cần đọc raw JSON, không cần hiểu classifier/profile model và về trạng thái đích không cần chạy Python/terminal.

### Chrome — hiện tại 0.6.1

Path:

```text
browser_extension/youtube_home_collector/
```

Auto-on passive capture:

```text
Home
natural Watch-page Up Next
Subscriptions / Channels
```

Không auto-click/play/scroll/like/comment/subscribe.

Current transport:

```text
Chrome Extension
→ http://127.0.0.1:8765
→ scripts/homepage/home_bridge.py
→ local enrichment/classification/profile
→ sanitized /v1/profile sync
```

Đây là **transitional architecture**.

Target Chrome transport:

```text
Chrome Extension
→ configured central server
→ raw browser ingest endpoint
→ central analysis
```

Sau refactor participant Chrome không cần local Python bridge.

### Android — hiện tại source 0.2.0

Path:

```text
android_collector/
```

Collector dùng Android `AccessibilityService`, chỉ cho:

```text
com.google.android.youtube
```

Events/evidence:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
rootInActiveWindow
bounded AccessibilityNodeInfo tree
```

Không gọi:

```text
performAction()
dispatchGesture()
ACTION_CLICK
ACTION_SCROLL_*
ACTION_SET_TEXT
```

Android Settings hiện có:

```text
Server URL
Project token
Participant ID
Profile slot
Auto sync ON/OFF
HTTP development override
```

Flow:

```text
YouTube natural use
→ bounded snapshot
→ canonical local JSONL
→ local pending queue
→ POST /v1/android/snapshot
→ retry nếu mạng/server lỗi
```

`device_id` tự sinh một lần. ADB/CMD bridge chỉ còn debug/fixture fallback.

APK chỉ được coi là ready khi `.github/workflows/android-apk.yml` chạy `assembleDebug` xanh và tạo artifact thật.

---

# 3. Trung tâm phân tích

## 3.1 Ingestion server

Module:

```text
scripts/community/community_server.py
```

Current server version:

```text
YouTubeLibraryCommunity/1.1
```

Endpoints:

```text
GET  /health
POST /v1/android/snapshot
POST /v1/profile
```

### `/v1/android/snapshot`

Nhận raw bounded Android Accessibility evidence và lưu riêng:

```text
data/android_ingest/
```

Raw Android không đi thẳng vào creator report.

### `/v1/profile`

Nhận analyzed/sanitized profile summary và cập nhật:

```text
data/community_profiles/
```

sau đó rebuild Creator Community Intelligence.

### Browser endpoint cần thêm

Target:

```text
POST /v1/browser/snapshot
```

để Chrome bỏ local bridge và dùng cùng central pipeline với Android.

## 3.2 Central analysis pipeline

Target canonical pipeline:

```text
raw browser/android evidence
        ↓
platform parser / normalization
        ↓
normalized Home / Up Next / Subscriptions evidence
        ↓
YouTube metadata enrichment
        ↓
content + intent classification
        ↓
per-profile daily observation
        ↓
Today / 7d / 30d / Long-term
        ↓
trend state
baseline / emerging / rising / stable / cooling / dormant / revived
        ↓
current longitudinal profile
        ↓
participant-balanced community aggregation
        ↓
creator opportunity report
```

Existing analysis modules:

```text
scripts/classification/
scripts/enrichment/
scripts/profile/
scripts/community/
taxonomy/
schemas/
```

Legacy/transitional:

```text
scripts/homepage/        # browser local bridge path
scripts/android/         # ADB/fixture/debug tools
scripts/viewer/          # synthetic sandbox only
```

## 3.3 Participant balancing

Một participant có thể có nhiều browser profiles/device slots.

```text
Participant A
├── Browser A1
├── Browser A2
└── Android A3

Participant B
└── Browser B1
```

Không được coi ví dụ trên là 4 independent humans.

Rule:

```text
mỗi participant = cùng một tổng community weight
nhiều profiles cùng participant
→ chia participant weight theo profile quality/certainty
```

Report luôn có:

```text
participant_count
profile_count
usable_participant_count
usable_profile_count
```

---

# 4. Creator output contract — giữ xuyên suốt dự án

Primary human-facing UI:

```text
data/community_reports/current.html
```

Machine/API representation:

```text
data/community_reports/current.json
```

Creator không cần đọc raw/profile JSON.

Dashboard top-level:

```text
COMMUNITY OVERVIEW
Participants
Profiles
Usable participants
Usable profiles

TOP CONTENT OPPORTUNITIES
#1 Lane A
#2 Lane B
#3 Lane C
```

Mỗi lane cần có:

```text
segment/category
matched participants
matched profiles
participant coverage
participant-balanced coverage
community opportunity score
fit band
core keywords
core tags
expansion keywords
top intent/format
trend breadth/momentum
certainty / limitations
```

Creator summary cần giữ ba hướng:

```text
Recommended Anchor
Recommended Bridge
Controlled Expansion
```

Ý nghĩa đúng:

> Hướng nội dung này đang có support/fit cao trong community panel quan sát được.

Không diễn giải:

> Có X% xác suất YouTube sẽ recommend hoặc video sẽ có X views.

Long-term calibration có thể bổ sung creator-owned organic analytics sau publication, nhưng collector không tạo engagement.

---

# 5. Data policy / repository cleanup

`data/` là **runtime workspace**, không phải source tree.

Git chỉ giữ:

```text
data/README.md
```

Toàn bộ raw/intermediate/profile/report runtime được `.gitignore`; code tự tạo thư mục khi cần.

Các lớp có thể tồn tại lúc chạy:

```text
raw ingest
→ normalized/enriched/classified intermediates
→ longitudinal profile state
→ community profile state
→ creator report
```

Người dùng không cần đọc các lớp trung gian.

Human-facing product output chỉ ưu tiên:

```text
current.html
```

`current.json` dành cho API/code. Per-profile/raw reports chỉ là drill-down/debug/provenance khi cần.

---

# 6. Current status

```text
Chrome passive collector                    IMPLEMENTED 0.6.1
Chrome direct central upload                PENDING
Chrome local bridge/profile path            IMPLEMENTED, TRANSITIONAL

Android Accessibility collector source      IMPLEMENTED 0.2.0
Android auto server settings/sync queue      IMPLEMENTED
Android APK build                            MUST VERIFY CI ARTIFACT
Android raw central ingest                   IMPLEMENTED
Android node → normalized video parser       PENDING REAL FIXTURES
Android longitudinal profile                 PENDING PARSER

Community ingestion server                  IMPLEMENTED v1.1
Participant-balanced community aggregator   IMPLEMENTED
Creator current.html/current.json            INITIAL IMPLEMENTATION

Synthetic Viewer Robot                      SANDBOX ONLY
```

---

# 7. Immediate engineering sequence

Ưu tiên theo thứ tự:

```text
1. Verify Android APK build thật trên GitHub Actions.
2. Lấy Android raw snapshots qua auto-sync và build fixture-tested node parser.
3. Chuẩn hóa Android raw → normalized Home/Watch/Subscriptions evidence.
4. Thêm POST /v1/browser/snapshot và Server Settings vào Chrome extension.
5. Chuyển Chrome khỏi local Python bridge sang direct central upload.
6. Chuyển enrichment/classification/temporal profile thành central canonical pipeline cho cả Chrome + Android.
7. Giữ /v1/profile như internal/analyzed profile contract giữa analysis stage và aggregator.
8. Hoàn thiện Creator Dashboard thành UI duy nhất cho creator; profile/raw chỉ drill-down.
9. Thêm retention/cleanup policy cho raw/intermediate central data.
10. Sau khi distributed real collectors ổn định mới quay lại synthetic sandbox nếu còn cần.
```

---

# 8. Safety / interpretation boundary

- Collector chỉ đo lường natural participant use; không tạo traffic/engagement.
- Chrome/Android không auto-click/play/like/comment/subscribe.
- Android Accessibility chỉ giới hạn YouTube package.
- Participant biết mình tham gia và có pause/resume/auto-sync settings.
- Không cần Google email/password/cookie ở community identity.
- Synthetic viewer không phải ground truth và không rewrite observed profiles.
- Nhiều profile của cùng một participant không được tính thành nhiều người độc lập.
- Community coverage/opportunity là research heuristic trên panel, không phải YouTube internal probability.

---

# 9. Câu mở đầu cho lần tiếp tục

> Đọc `README.md` và `PLAN.md`. Dự án chỉ còn 2 khối chính: Participant Collectors (Chrome + Android) và Central Analysis. Android 0.2.0 đã có auto-sync raw snapshot vào `/v1/android/snapshot`; Chrome 0.6.1 vẫn dùng local bridge và cần refactor sang direct central `/v1/browser/snapshot`. `data/` là runtime-only; creator chỉ cần `community_reports/current.html`. Tiếp tục theo Immediate engineering sequence.
