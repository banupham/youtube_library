# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> Đây là checkpoint canonical. `PROJECT_PLAN.md` giữ roadmap gốc; file này phản ánh kiến trúc đã được chỉnh theo dữ liệu thực tế.

# 1. Kiến trúc canonical mới

Trục chính của dự án không phải “một người test nhiều profile rồi nhân thành audience synthetic”.

Trục chính là một **consenting distributed profile panel**:

```text
PARTICIPANT A                 PARTICIPANT B                 PARTICIPANT C
browser / future Android     browser / future Android     browser / future Android
      │                             │                             │
      ▼                             ▼                             ▼
PASSIVE READ-ONLY COLLECTOR   PASSIVE READ-ONLY COLLECTOR   PASSIVE READ-ONLY COLLECTOR
      │                             │                             │
      ▼                             ▼                             ▼
LOCAL PROFILE ENGINE          LOCAL PROFILE ENGINE          LOCAL PROFILE ENGINE
Home / Up Next / Subs         Home / Up Next / Subs         Home / Up Next / Subs
Today / 7d / 30d / Long       Today / 7d / 30d / Long       Today / 7d / 30d / Long
      │                             │                             │
      └──────── sanitized profile summaries ─────────────────────┘
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

Creator cuối cùng chỉ cần biết:

```text
cộng đồng hiện có bao nhiêu participants / profiles
content lane nào đang xuất hiện ở nhiều participants
key/keyword nào là core
creator tags nào lặp lại
key nào đang rising/emerging để mở rộng
intent/format nào phù hợp
lane nào nên anchor / bridge / controlled expansion
mức certainty / limitation của panel
```

Không gọi các score này là xác suất YouTube recommendation/view.

---

# 2. Participant khác Profile

Đây là quy tắc bắt buộc.

```text
Participant A
├── Profile A1
├── Profile A2
└── Profile A3

Participant B
└── Profile B1
```

Không được coi ví dụ trên là 4 người độc lập.

Community engine dùng **participant-balanced weighting**:

```text
mỗi participant = cùng một tổng community weight
nhiều profile cùng participant
→ chia tổng weight đó theo profile quality/certainty
```

Creator report luôn hiển thị cả:

```text
participant_count
profile_count
usable_participant_count
usable_profile_count
```

Một tester có nhiều profile vẫn hữu ích để nghiên cứu recommendation states, nhưng không được làm community sample giả lớn hơn số người tham gia thật.

---

# 3. Dữ liệu thật hiện tại lấy từ đâu

Observed data là dữ liệu YouTube thật trả về trên các profile mà participant tự sử dụng và cho phép collector đọc.

Browser profile hiện có thể đóng góp:

```text
Home recommendation exposure
Up Next recommendation exposure
Subscriptions feed / subscribed-channel affinity
Daily longitudinal evolution
```

YouTube Data API enrichment có thể bổ sung:

```text
description
tags
categoryId
topicDetails
publishedAt
views
likes
comments
```

Raw observations vẫn là panel evidence, không phải đại diện mặc định cho toàn bộ YouTube audience.

---

# 4. Natural/passive browser collector — extension 0.6.0

Extension hiện có hai mode.

## 4.1 Passive natural-use mode — ưu tiên

Opt-in một lần trong popup:

```text
Bật passive collection tự động
```

Sau đó participant dùng YouTube bình thường.

Collector KHÔNG:

```text
tự mở tab
tự mở video
tự play
tự click
tự like/comment/subscribe
```

Collector chỉ đọc surface participant tự truy cập.

### Home

Participant tự mở Home và tự scroll.

Sau khoảng thời gian quan sát, extension đọc các video card đã load trong DOM.

Daily cap ban đầu:

```text
Home <= 2 passive snapshots/day
```

Không auto-scroll trong passive mode.

### Up Next

Participant tự mở một video/watch page.

Extension chờ page load rồi đọc recommendation DOM trong secondary column.

```text
/watch?v=...
→ passive Up Next snapshot
```

Không request random watch page/replay trong passive mode.

Daily cap ban đầu:

```text
<= 8 naturally opened watch pages/day
```

### Subscriptions

Nếu participant tự mở:

```text
/feed/subscriptions
/feed/channels
```

collector có thể đọc read-only snapshot tương ứng.

Daily cap:

```text
Subscriptions <= 1/day
Channels <= 1/day
```

## 4.2 Manual fallback

Pipeline manual cũ vẫn giữ để debug/test:

```text
manual Home scroll
manual Subscriptions fetch
random Home seed → watch HTML replay
```

Manual replay không phải nguồn natural panel ưu tiên về lâu dài.

---

# 5. Local Profile Engine — Phase 5.5

Mỗi participant/device vẫn xử lý profile local trước.

```text
Home
+
Up Next
+
Subscriptions
↓
API enrichment
↓
classifier
↓
session profile
↓
daily observation
↓
Today / 7d / 30d / Long-term
↓
trend state
↓
current longitudinal profile
```

Current files:

```text
data/profile_library/profile_<id>.json
data/profile_library/profile_<id>.history.jsonl
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
```

Temporal states:

```text
baseline
emerging
rising
stable
cooling
dormant
revived
```

Current versions:

```text
extension                         0.6.0
local bridge                      0.8
longitudinal profile analysis     2.5.0
session creator profile           2.1.0
```

Phase 5.5 validation nhiều ngày vẫn tiếp tục.

---

# 6. Privacy-preserving community submission

Raw browser/account data không cần gửi lên server trung tâm.

Schema:

```text
schemas/community_profile_submission.v1.schema.json
```

Submitter:

```text
scripts/community/submit_profile.py
```

Mỗi local installation tự tạo random:

```text
participant_id
device_id
```

lưu tại:

```text
data/collector_identity.json
```

File này git-ignored.

Sanitized community payload chỉ gửi:

```text
participant_id
device_id
profile_id / derived profile_key
analysis version
certainty
daily observation count
interest weights + trends
intent weights
keyword trends
tag trends
```

Không gửi theo protocol v1:

```text
cookies
password
Google email/account identifier
profile display label
raw Home/Up Next video rows
raw browsing/watch history
subscribed-channel names/list
```

---

# 7. Automatic local → community sync

Module:

```text
scripts/community/collector_agent.py
```

Nhiệm vụ:

```text
watch data/profile_library/profile_*.json
↓
phát hiện profile current thay đổi
↓
build sanitized submission
↓
POST community server
```

Có thể chạy:

```bat
set "YT_LIBRARY_COMMUNITY_ENDPOINT=https://YOUR_SERVER"
set "YT_LIBRARY_COMMUNITY_TOKEN=YOUR_PROJECT_TOKEN"
python scripts\community\collector_agent.py
```

Hoặc để agent launch local bridge:

```bat
python scripts\community\collector_agent.py --launch-bridge --endpoint https://YOUR_SERVER
```

Agent không browse YouTube; nó chỉ auto-sync kết quả local collector.

---

# 8. Central Community Server

Module:

```text
scripts/community/community_server.py
```

Endpoint:

```text
POST /v1/profile
GET  /health
```

Chạy local/test:

```bat
set "YT_LIBRARY_COMMUNITY_TOKEN=RANDOM_SECRET"
python scripts\community\community_server.py --host 127.0.0.1 --port 8770
```

Nếu deploy internet:

```text
HTTPS reverse proxy
firewall
Bearer token
server-side storage backup
```

Không expose server HTTP unauthenticated trực tiếp ra internet.

Accepted profile submission sẽ replace current central snapshot của profile đó và rebuild creator report.

Central data:

```text
data/community_profiles/
data/community_reports/current.json
data/community_reports/current.html
```

Deployment data được git-ignore.

---

# 9. Creator Community Aggregator

Module:

```text
scripts/community/build_community_report.py
```

Đây là module tổng mà creator-facing architecture cần.

Nó đọc tất cả current sanitized community profiles và aggregate theo participant-balanced weighting.

Mỗi content lane trả:

```text
segment_key
category
matched_profile_count
matched_participant_count
profile_coverage_ratio
participant_coverage_ratio
participant_balanced_coverage
participant_balanced_interest
trend_momentum
trend profile counts
community opportunity score
fit band
core keywords
core tags
expansion keywords
top intent
```

Ví dụ:

```text
Community key:
science_technology::tutorial

Participants matched: 8 / 12
Profiles matched:     13 / 21

Core keys:
AI video
creator workflow
YouTube automation

Core tags:
ai video
creator tools

Expansion keys:
agent workflow
AI voice

Fit band:
strong
```

Ý nghĩa đúng:

> Hướng nội dung này có support rộng trong community panel đang quan sát.

Không được diễn giải:

> Có X% xác suất YouTube sẽ hiển thị/video sẽ có view.

---

# 10. Creator UI contract

UI chính về sau là:

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

mỗi lane:
participants matched
profiles matched
core keys
core tags
expansion keys
trend breadth
intent
fit band
```

Sau đó mới drill-down:

```text
profile nào hỗ trợ lane
Home/Up Next/Subscriptions evidence
Today/7d/30d/Long
keyword/tag provenance
```

Người sáng tạo không cần đọc raw profile JSON hoặc từng robot.

---

# 11. Android collector direction

Android phải dùng cùng community submission protocol.

```text
Android collector
↓
local/sanitized profile state
↓
community_profile_submission.v1
↓
central server
```

Quan trọng:

Public YouTube Data API **không expose personalized Home recommendation feed**.

Vì vậy chưa được tuyên bố Android native app có thể lấy chính xác Home/Up Next như browser extension nếu chưa có legitimate read-only interface được validate.

Android v1 nên bắt đầu từ những surface có thể thu hợp lệ/read-only, ví dụ:

```text
officially authorized subscription/account metadata nếu API cho phép
participant-controlled web collector container nếu auth/platform policy phù hợp
```

Không mặc định dùng Android Accessibility để scrape YouTube app vì nó có thể thu cả dữ liệu UI nhạy cảm ngoài phạm vi.

Chi tiết:

```text
docs/DISTRIBUTED_PROFILE_COLLECTION.md
```

---

# 12. Viewer Robot / Phase 6 — vai trò đã điều chỉnh

Code Phase 6 slice 1 vẫn tồn tại:

```text
schemas/viewer_robot.v1.schema.json
taxonomy/interest_relations.v1.json
scripts/viewer/generate_viewers.py
scripts/viewer/summarize_viewer_batch.py
tests/test_viewer_generator.py
```

Nhưng synthetic viewers KHÔNG làm tăng số evidence thật.

```text
20 real community profiles
→ 10,000 robots
```

vẫn chỉ có evidence thật từ 20 profiles/participants tương ứng.

Viewer Robot chỉ là:

```text
scenario testing
sensitivity testing
future offline feed experiments
```

Nó không được rewrite canonical observed/community data và không phải nguồn chính để creator quyết định khi community evidence thực có sẵn.

Trước mắt ưu tiên hoàn thiện distributed natural collection + community aggregator trước khi mở rộng Phase 7–9.

---

# 13. Current important modules

```text
# Browser collector
browser_extension/youtube_home_collector/manifest.json        0.6.0
browser_extension/youtube_home_collector/background.js
browser_extension/youtube_home_collector/passive_collector.js
browser_extension/youtube_home_collector/popup.html
browser_extension/youtube_home_collector/popup_passive.js
browser_extension/youtube_home_collector/popup.js
browser_extension/youtube_home_collector/subscriptions.js

# Local profile engine
scripts/homepage/home_bridge.py
scripts/profile/build_consolidated_profile.py
scripts/profile/build_temporal_profile.py

# Distributed community network
schemas/community_profile_submission.v1.schema.json
scripts/community/submit_profile.py
scripts/community/collector_agent.py
scripts/community/community_server.py
scripts/community/build_community_report.py
docs/DISTRIBUTED_PROFILE_COLLECTION.md
tests/test_community_report.py

# Synthetic sandbox
scripts/viewer/generate_viewers.py
scripts/viewer/summarize_viewer_batch.py
```

---

# 14. Tests / CI

Workflow:

```text
.github/workflows/python-tests.yml
```

Checks:

```text
Python compile
community schema JSON
viewer schema JSON
extension manifest JSON
extension JavaScript syntax
unit tests
```

Community tests khóa:

```text
participant balancing
participant vs profile counts
community lane aggregation
rising/emerging expansion keys
```

---

# 15. Immediate next validation

Không cần quay lại thiết kế Viewer Robot ngay.

## A. Browser passive collector

Test ít nhất hai independent participants/devices nếu có thể.

Mỗi participant:

```text
reload extension 0.6.0
enable passive collector
run local bridge
use YouTube normally
```

Check:

```text
Home passive snapshots đúng video card
Up Next chỉ đến từ watch pages participant tự mở
Subscriptions snapshot hợp lý
daily caps hoạt động
không auto-navigation/player
profile temporal update vẫn đúng
```

## B. Community pipeline

Central machine:

```bat
set "YT_LIBRARY_COMMUNITY_TOKEN=..."
python scripts\community\community_server.py --host 0.0.0.0 --port 8770
```

Participant machine:

```bat
set "YT_LIBRARY_COMMUNITY_ENDPOINT=https://..."
set "YT_LIBRARY_COMMUNITY_TOKEN=..."
python scripts\community\collector_agent.py
```

Check:

```text
Participant A 3 profiles
Participant B 1 profile
→ participant_count = 2
→ profile_count = 4
→ A total aggregate weight không > B chỉ vì có 3 profiles
```

## C. Creator report

Check:

```text
core keys có đúng shared semantic không
core tags có noisy/stale tags không
expansion keys có thật sự rising/emerging không
participant coverage có dễ hiểu không
fit-band thresholds có cần tune không
```

---

# 16. Next engineering steps

Ưu tiên theo thứ tự:

```text
1. Validate passive browser collector 0.6.0
2. Validate community server với >=2 independent participants
3. Make community HTML the main Creator Dashboard
4. Add profile drill-down/provenance links
5. Build Android adapter against the same submission protocol
6. Add channel affinity / freshness / language / duration dimensions
7. Revisit Phase 6 synthetic robustness only as sandbox support
```

---

# 17. Safety / data boundary

- Participant phải opt-in collector.
- Browser passive mode chỉ quan sát natural navigation; không tự tạo traffic.
- Không tự click/play/like/comment/subscribe/unsubscribe.
- Không dùng project profiles làm initial-engagement network.
- Community server không cần cookies/password/Google account IDs.
- Participant ID là random project ID, không phải email.
- Một participant có nhiều profiles không được tính thành nhiều independent humans trong aggregate weighting.
- Community fit/coverage không phải xác suất view/recommendation.
- External real audience vẫn là population ngoài dự án.
- Synthetic Viewer Robot chỉ là sandbox, không phải ground truth.

---

# 18. Câu mở đầu cho cuộc trò chuyện sau

> Đọc `PLAN.md`. Kiến trúc hiện tại là distributed natural profile collection: extension 0.6.0 passive collector → local longitudinal profile → sanitized community sync → participant-balanced creator community report. Tiếp tục validate passive collector/community server và xây Creator Community Dashboard; Viewer Robot chỉ là synthetic sandbox phụ.
