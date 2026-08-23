# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> Đây là checkpoint canonical. `PROJECT_PLAN.md` giữ roadmap gốc; file này phản ánh kiến trúc hiện tại sau khi chuyển trọng tâm sang distributed natural profile collection.

# 1. Kiến trúc canonical

Trục chính của dự án là một **consenting distributed profile panel** từ nhiều participant/device thật.

```text
PARTICIPANT A                  PARTICIPANT B                  PARTICIPANT C
Browser + Android             Browser + Android             Browser + Android
      │                              │                              │
      ▼                              ▼                              ▼
PASSIVE READ-ONLY COLLECTORS   PASSIVE READ-ONLY COLLECTORS   PASSIVE READ-ONLY COLLECTORS
      │                              │                              │
      ▼                              ▼                              ▼
LOCAL PROFILE STATE            LOCAL PROFILE STATE            LOCAL PROFILE STATE
      │                              │                              │
      └──────────── sanitized profile summaries ───────────────────┘
                                     │
                                     ▼
                          COMMUNITY INGESTION SERVER
                                     │
                                     ▼
                      PARTICIPANT-BALANCED AGGREGATION
                                     │
                                     ▼
                          CREATOR COMMUNITY INTELLIGENCE
```

Creator cuối cùng cần thấy:

```text
bao nhiêu participants / profiles đang có dữ liệu
content lane nào xuất hiện ở nhiều participants
core keys / keywords / tags
expansion keys đang rising/emerging
intent/format phù hợp
anchor / bridge / controlled expansion
certainty và limitation của panel
```

Không gọi các score này là xác suất YouTube recommendation/view.

---

# 2. Participant khác Profile

```text
Participant A
├── Browser Profile A1
├── Browser Profile A2
└── Android Slot A3

Participant B
└── Browser Profile B1
```

Không được coi ví dụ trên là 4 người độc lập.

Community engine dùng **participant-balanced weighting**:

```text
mỗi participant = cùng một tổng community weight
nhiều profile/device slots cùng participant
→ chia tổng weight theo profile quality/certainty
```

Creator report luôn hiển thị:

```text
participant_count
profile_count
usable_participant_count
usable_profile_count
```

---

# 3. Browser collector — extension 0.6.1

## Auto-on

```text
install / reload extension
→ passive collection mặc định ON
→ participant mở youtube.com
→ collector tự chạy trên route hiện tại
```

Popup chỉ có pause/resume; không còn runtime opt-in checkbox.

## Natural-use rule

Collector không tự:

```text
open tab/video
play
click
like/comment/subscribe
auto-scroll trong passive mode
```

Nó chỉ đọc những surface participant tự mở.

Current browser evidence:

```text
Home DOM
natural Watch-page Up Next DOM
Subscriptions / Channels DOM
manual fallback/replay chỉ dùng debug
```

Browser raw evidence đi qua local Python profile engine:

```text
Home + Up Next + Subscriptions
→ API enrichment
→ classifier
→ daily observation
→ Today / 7d / 30d / Long-term
→ baseline/emerging/rising/stable/cooling/dormant/revived
→ current longitudinal profile
```

Current versions:

```text
browser extension                  0.6.1
local bridge                       0.8
longitudinal profile analysis      2.5.0
session creator profile            2.1.0
```

---

# 4. Android collector — AccessibilityService v0.1.0

Android chính thức là một collector trong cùng hệ sinh thái.

```text
participant cài Android collector
→ app hiển thị disclosure về AccessibilityService
→ participant bấm Đồng ý & mở Cài đặt trợ năng
→ participant bật service một lần
→ từ đó service tự chạy khi YouTube native app đang mở
```

YouTube package bị khóa cứng:

```text
com.google.android.youtube
```

Android collector sử dụng:

```text
AccessibilityService
rootInActiveWindow
AccessibilityNodeInfo tree
FLAG_REPORT_VIEW_IDS
```

Service config:

```text
android_collector/app/src/main/res/xml/accessibility_service_config.xml
```

Events:

```text
TYPE_WINDOW_STATE_CHANGED
TYPE_WINDOW_CONTENT_CHANGED
TYPE_VIEW_SCROLLED
```

Service chỉ đọc node tree. Không có code:

```text
performAction()
dispatchGesture()
GLOBAL_ACTION_*
ACTION_CLICK
ACTION_SCROLL_*
ACTION_SET_TEXT
```

## Android privacy boundary

Android v0.1 không đọc package ngoài YouTube và không gửi raw node tree lên community server.

Snapshot chỉ lưu app-internal:

```text
files/youtube_accessibility_snapshots/YYYY-MM-DD.jsonl
```

Mỗi snapshot dùng schema:

```text
schemas/android_accessibility_snapshot.v1.schema.json
```

Fields chính:

```text
captured_at
source_package
surface_guess + confidence/evidence
tree_signature
bounded accessibility nodes
```

Node evidence có thể gồm:

```text
text
contentDescription
viewIdResourceName
className
selected/clickable/scrollable
child_count
bounds
depth
```

Traversal cap:

```text
<= 450 retained nodes
<= depth 18
```

Strings được length-limit. Snapshot trùng tree signature bị bỏ qua.

Initial daily caps:

```text
home            4/day
watch          24/day
subscriptions   4/day
shorts         12/day
search          8/day
unknown         6/day
```

Raw count không làm participant có community weight lớn hơn vì aggregator vẫn participant-balanced.

## Surface detector Android

Current provisional surfaces:

```text
home
watch
subscriptions
shorts
search
unknown
```

Detector hiện chỉ là heuristic từ selected labels / text / contentDescription / view IDs.

Không hard-code video-card parser trước khi có fixture thật vì native YouTube Accessibility tree thay đổi theo app version/locale và không bảo đảm map 1:1 vào Android Views.

## Android validation flow — NEXT

```text
2+ Android devices / YouTube versions
→ tự dùng Home/Watch/Subscriptions/Shorts/Search
→ lấy một số node-tree snapshots local
→ inspect stable node/view-id/accessibility patterns
→ fixture parser tests
→ node tree → normalized video cards/surfaces
→ Android daily profile
→ sanitized community_profile_submission.v1
→ automatic community sync
```

Tool inspect local export:

```text
scripts/android/inspect_accessibility_snapshots.py
```

Android current module:

```text
android_collector/
├── app/src/main/AndroidManifest.xml
├── app/src/main/res/xml/accessibility_service_config.xml
├── app/src/main/java/com/youtube/library/collector/
│   ├── MainActivity.kt
│   ├── YouTubeAccessibilityService.kt
│   ├── NodeTreeExtractor.kt
│   ├── SurfaceDetector.kt
│   ├── SnapshotModels.kt
│   └── LocalSnapshotStore.kt
└── README.md
```

### Android account-switch limitation

v0.1 không scrape Google email/account name để định danh account trong YouTube app.

Một app installation hiện được coi là một Android collection slot. Nếu participant thường xuyên switch nhiều YouTube account trong cùng app thì evidence có thể trộn. Future solution nên là explicit non-sensitive local slot selector, không scrape account identity.

### Play policy note

Collector không phải accessibility tool dành cho disability support (`isAccessibilityTool=false`). Vì dùng AccessibilityService cho mục đích data collection, Android app phải có prominent disclosure + affirmative consent nếu phân phối qua Google Play, cùng Accessibility declaration/Data Safety/Privacy Policy phù hợp.

---

# 5. Community submission protocol

Schema:

```text
schemas/community_profile_submission.v1.schema.json
```

Browser submitter:

```text
scripts/community/submit_profile.py
```

Installation tạo random:

```text
participant_id
device_id
```

Không dùng Google account/email làm participant identity.

Sanitized community payload chỉ cần:

```text
participant_id
device_id
profile_key
analysis version
certainty
daily observation count
interest weights + trends
intent weights
keyword trends
tag trends
```

Protocol không gửi:

```text
cookies/password
Google email/account identifier
raw browsing/watch history
raw Home/Up Next rows
raw Android Accessibility node tree
subscribed-channel names/list
```

Android sẽ emit cùng `community_profile_submission.v1` sau khi node-to-video parser + Android local profile engine được validate.

---

# 6. Automatic local → community sync

Browser/current desktop flow:

```text
scripts/community/collector_agent.py
```

```text
watch profile_library/profile_*.json
→ build sanitized submission
→ POST central community server
```

Central server:

```text
scripts/community/community_server.py
POST /v1/profile
GET /health
```

Android v0.1 chưa có `INTERNET` permission và chưa sync raw/accessibility snapshots. Network sync chỉ được thêm ở giai đoạn đã có sanitized Android profile output.

---

# 7. Creator Community Aggregator

Module:

```text
scripts/community/build_community_report.py
```

Mỗi content lane trả:

```text
segment_key
matched_profile_count
matched_participant_count
profile_coverage_ratio
participant_coverage_ratio
participant_balanced_coverage
participant_balanced_interest
trend_momentum
community opportunity score
fit band
core keywords
core tags
expansion keywords
top intent
```

Ý nghĩa đúng:

> Hướng nội dung này có support rộng trong community panel đang quan sát.

Không được diễn giải thành xác suất YouTube impressions/views.

Creator UI chính về sau:

```text
COMMUNITY OVERVIEW
Participants                    N
Profiles                        N
Usable participants             N
Usable profiles                 N

TOP CONTENT OPPORTUNITIES
#1 Lane A
#2 Lane B
#3 Lane C
```

Drill-down mới hiển thị profile/surface/provenance chi tiết.

---

# 8. Viewer Robot — sandbox phụ

Synthetic code vẫn giữ:

```text
schemas/viewer_robot.v1.schema.json
taxonomy/interest_relations.v1.json
scripts/viewer/generate_viewers.py
scripts/viewer/summarize_viewer_batch.py
```

Nhưng synthetic viewers không làm tăng evidence thật và không rewrite community truth.

Chỉ dùng cho:

```text
scenario testing
sensitivity testing
offline simulation experiments
```

Ưu tiên hiện tại là distributed natural collection từ browser + Android và community intelligence.

---

# 9. Tests / guardrails

CI:

```text
.github/workflows/python-tests.yml
```

Checks hiện gồm:

```text
Python compile
community/viewer/android JSON schemas
extension manifest
Android XML well-formedness
browser JS syntax
community tests
viewer tests
Android guardrail tests
```

Android guardrail test:

```text
tests/test_android_collector_guardrails.py
```

Khóa các yêu cầu:

```text
packageNames = com.google.android.youtube
canRetrieveWindowContent = true
isAccessibilityTool = false
không interaction Accessibility APIs
không INTERNET / overlay / QUERY_ALL_PACKAGES ở Android v0.1
```

---

# 10. Immediate next engineering sequence

```text
1. Build/install Android collector v0.1 on one test device
2. Enable AccessibilityService and use YouTube naturally
3. Obtain local Home/Watch/Subscriptions/Shorts/Search node fixtures
4. Validate surface detector and identify stable video-card patterns
5. Implement Android node → normalized YouTube surface parser
6. Build Android daily/temporal profile compatible with community schema
7. Add sanitized Android community sync
8. Validate participant aggregation with Browser + Android data from >=2 real participants
9. Make Community HTML the primary Creator Dashboard
10. Package browser desktop bridge/agent as background service
```

Do not return to large synthetic population work before real distributed collectors are stable.

---

# 11. Data / safety boundary

- Browser collection auto-on after participant installs collector; participant can pause/resume.
- Android collection auto-on after participant explicitly enables AccessibilityService; participant can pause/resume.
- Android AccessibilityService is restricted to YouTube package and read-only node retrieval.
- No automatic click/play/gesture/like/comment/subscribe/unsubscribe.
- No project profile is used as an initial-engagement network.
- Raw Android node tree remains local in v0.1.
- Community server does not need cookie/password/Google account identity.
- Multiple profiles/devices from one participant do not count as multiple independent humans.
- Community fit/coverage is panel evidence, not probability of view/recommendation.
- Viewer Robot remains sandbox, not ground truth.

---

# 12. Câu mở đầu cho cuộc trò chuyện sau

> Đọc `PLAN.md`. Browser extension 0.6.1 đã auto-on. Android Accessibility collector v0.1 đã có nền: YouTube-only AccessibilityService → bounded local node-tree snapshot → provisional surface detector. Tiếp tục bằng việc lấy fixture node tree thật từ Android, viết node-to-video-card parser, rồi xây Android local profile + sanitized community sync.
