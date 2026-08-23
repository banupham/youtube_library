# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> Đây là checkpoint canonical. `PROJECT_PLAN.md` giữ roadmap gốc; file này phản ánh kiến trúc hiện tại sau khi chuyển trọng tâm sang distributed natural profile collection.

# 1. Kiến trúc canonical

Trục chính của dự án là một **consenting distributed profile panel**:

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

---

# 3. Dữ liệu thật hiện tại

Observed data là recommendation/affinity data thật YouTube trả về trên profile participant tự sử dụng.

Browser collector hiện đóng góp:

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

Raw observations là panel evidence, không mặc định đại diện toàn bộ YouTube audience.

---

# 4. Browser passive collector — extension 0.6.1

## 4.1 Auto-on participation model

Participant đã biết và chủ động tham gia cộng đồng khi cài collector. Vì vậy runtime không còn checkbox opt-in.

```text
install / reload extension
→ passive collection mặc định ON
→ participant mở youtube.com
→ collector tự kích hoạt cho route hiện tại
```

Nếu participant muốn ngừng tạm thời, popup chỉ có:

```text
Tạm dừng thu thập
Tiếp tục thu thập
```

Trạng thái `paused=false/true` được lưu local và giữ qua browser restart.

## 4.2 Natural-use rule

Collector KHÔNG:

```text
tự mở tab
tự mở video
tự play
tự click
tự like/comment/subscribe
tự auto-scroll trong passive mode
```

Collector chỉ đọc surface participant tự truy cập.

### Home

```text
participant tự mở Home / tự scroll
→ sau thời gian chờ collector đọc video cards đã load
```

Daily cap ban đầu:

```text
Home <= 2 passive snapshots/day
```

### Up Next

```text
participant tự mở /watch?v=...
→ collector đọc recommendation DOM ở secondary column
```

Không random watch-page/replay trong passive mode.

Daily cap:

```text
Up Next <= 8 naturally opened watch pages/day
```

### Subscriptions

Nếu participant tự mở:

```text
/feed/subscriptions
/feed/channels
```

collector đọc read-only snapshot tương ứng.

Daily cap:

```text
Subscriptions <= 1/day
Channels <= 1/day
```

## 4.3 Manual fallback

Pipeline manual cũ vẫn giữ chỉ để debug/test:

```text
manual Home scroll
manual Subscriptions fetch
random Home seed → watch HTML replay
```

Manual replay không phải nguồn natural panel ưu tiên.

---

# 5. Local Profile Engine — Phase 5.5

Mỗi participant/device xử lý profile local trước:

```text
Home + Up Next + Subscriptions
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

Files:

```text
data/profile_library/profile_<id>.json
data/profile_library/profile_<id>.history.jsonl
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
```

Trend states:

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
browser extension                  0.6.1
local bridge                       0.8
longitudinal profile analysis      2.5.0
session creator profile            2.1.0
```

Phase 5.5 validation nhiều ngày tiếp tục song song.

---

# 6. Community submission protocol

Raw browser/account data không cần gửi lên server trung tâm.

Schema:

```text
schemas/community_profile_submission.v1.schema.json
```

Submitter:

```text
scripts/community/submit_profile.py
```

Mỗi installation tự tạo random:

```text
participant_id
device_id
```

lưu local tại:

```text
data/collector_identity.json
```

Sanitized payload gửi:

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

Protocol v1 không gửi:

```text
cookies
password
Google email/account identifier
profile display label
raw Home/Up Next rows
raw browsing/watch history
subscribed-channel names/list
```

---

# 7. Automatic local → community sync

Module:

```text
scripts/community/collector_agent.py
```

Flow:

```text
watch data/profile_library/profile_*.json
↓
profile current thay đổi
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

Lưu ý: extension auto-start khi truy cập YouTube, nhưng Python local bridge/agent hiện vẫn cần chạy. Bước triển khai participant hoàn chỉnh về sau nên đóng gói bridge + sync agent thành background desktop service/startup app để participant không cần terminal.

---

# 8. Central Community Server

Module:

```text
scripts/community/community_server.py
```

Endpoints:

```text
POST /v1/profile
GET  /health
```

Central storage/report:

```text
data/community_profiles/
data/community_reports/current.json
data/community_reports/current.html
```

Nếu deploy internet:

```text
HTTPS reverse proxy
firewall
auth token
server-side backup
```

Không expose HTTP unauthenticated trực tiếp ra Internet.

---

# 9. Creator Community Aggregator

Module:

```text
scripts/community/build_community_report.py
```

Aggregate theo participant-balanced weighting.

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

Fit band: strong
```

Ý nghĩa:

> Hướng nội dung này có support rộng trong community panel đang quan sát.

Không được diễn giải:

> Có X% xác suất YouTube sẽ hiển thị/video sẽ có view.

---

# 10. Creator UI contract

UI chính:

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

Mỗi lane hiển thị:

```text
participants matched
profiles matched
core keys
core tags
expansion keys
trend breadth
intent
fit band
```

Drill-down mới hiển thị profile/surface/provenance chi tiết.

---

# 11. Android direction

Android phải dùng cùng community submission protocol:

```text
Android collector
↓
local/sanitized profile state
↓
community_profile_submission.v1
↓
central server
```

Public YouTube Data API không expose personalized Home recommendation feed, nên chưa được tuyên bố Android native app có thể lấy Home/Up Next giống browser nếu chưa có legitimate read-only interface được validate.

Không mặc định dùng Android Accessibility để scrape app YouTube vì có thể thu dữ liệu UI nhạy cảm ngoài phạm vi.

Chi tiết:

```text
docs/DISTRIBUTED_PROFILE_COLLECTION.md
```

---

# 12. Viewer Robot — vai trò phụ

Phase 6 synthetic code vẫn giữ:

```text
schemas/viewer_robot.v1.schema.json
taxonomy/interest_relations.v1.json
scripts/viewer/generate_viewers.py
scripts/viewer/summarize_viewer_batch.py
```

Nhưng synthetic viewers không làm tăng evidence thật và không rewrite community truth.

Viewer Robot chỉ dùng cho:

```text
scenario testing
sensitivity testing
offline simulation experiments
```

Ưu tiên hiện tại là distributed natural collection + community intelligence.

---

# 13. Current important modules

```text
# Browser collector
browser_extension/youtube_home_collector/manifest.json        0.6.1
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

# Community network
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

# 14. Immediate validation

## Browser

Với ít nhất hai independent participants/devices:

```text
reload extension 0.6.1
KHÔNG mở popup để bật gì
mở YouTube và dùng bình thường
```

Check:

```text
passive collection tự chạy trên first YouTube visit
Home snapshot đúng cards
Up Next chỉ đến từ watch page participant tự mở
Subscriptions snapshot hợp lý
daily caps hoạt động
pause dừng capture
resume có thể schedule lại route hiện tại
không auto-navigation/player
```

## Community

Check case:

```text
Participant A 3 profiles
Participant B 1 profile
→ participant_count = 2
→ profile_count = 4
→ A không có tổng aggregate weight lớn hơn B chỉ vì nhiều profiles
```

## Creator report

Check:

```text
core keys đúng shared semantic
core tags không bị stale/noisy
expansion keys thật sự rising/emerging
participant coverage dễ hiểu
fit-band thresholds hợp lý
```

---

# 15. Next engineering steps

Ưu tiên:

```text
1. Validate extension 0.6.1 auto-on với >=2 participants
2. Package local bridge + community sync agent thành background desktop service/startup app
3. Validate community server với >=2 participants
4. Make community HTML the main Creator Dashboard
5. Add profile drill-down/provenance
6. Build Android adapter cùng submission protocol
7. Add channel affinity / freshness / language / duration dimensions
8. Revisit synthetic Viewer Robot only as sandbox support
```

---

# 16. Data/safety boundary

- Participation consent được xác lập khi người dùng chủ động tham gia/cài collector; không cần runtime opt-in checkbox.
- Participant luôn có nút pause/resume.
- Passive mode chỉ quan sát natural navigation; không tự tạo traffic.
- Không tự click/play/like/comment/subscribe/unsubscribe.
- Không dùng project profiles làm initial-engagement network.
- Community server không cần cookies/password/Google account IDs.
- Participant ID là random project ID, không phải email.
- Một participant có nhiều profiles không được tính thành nhiều independent humans.
- Community fit/coverage không phải xác suất view/recommendation.
- Synthetic Viewer Robot chỉ là sandbox, không phải ground truth.

---

# 17. Câu mở đầu cho cuộc trò chuyện sau

> Đọc `PLAN.md`. Kiến trúc hiện tại là distributed natural profile collection: extension 0.6.1 auto-on khi participant truy cập YouTube → local longitudinal profile → sanitized community sync → participant-balanced creator community report. Tiếp tục validate auto-on collector, đóng gói local bridge/agent thành background service và hoàn thiện Creator Community Dashboard.
