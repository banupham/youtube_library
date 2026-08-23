# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> Đây là checkpoint canonical để tiếp tục dự án ở các cuộc trò chuyện sau. Roadmap gốc đầy đủ vẫn ở `PROJECT_PLAN.md`.

## 1. Mục tiêu đã chốt

`youtube_library` là hệ thống nghiên cứu/offline gồm hai phía:

1. **Viewer side** — quan sát recommendation exposure của browser profile thật theo chế độ read-only, sau đó mô phỏng viewer synthetic/offline.
2. **Creator side** — dùng các profile/cluster để đề xuất chuỗi nội dung mới có semantic fit tốt với vùng recommendation đang quan sát.

Không cố sao chép chính xác taxonomy hay model nội bộ của YouTube. Taxonomy nội bộ được tối ưu cho:

```text
classification
→ profile understanding
→ profile evolution
→ content continuity
→ creator opportunity
→ viewer simulation
```

Không dùng robot để tạo traffic, view, click, like, comment hoặc tương tác giả trên YouTube thật.

---

## 2. Trạng thái hiện tại

### Milestone đã đạt

**Recommendation Profile Intelligence MVP**

Đã có pipeline Home + Up Next + YouTube API enrichment + classifier + consolidated profile + creative brief.

Tuy nhiên vừa xác định còn thiếu một phần quan trọng trước Phase 6:

# Phase 5.5 — Longitudinal Profile Evolution — NEXT

Hiện profile mới chỉ phản ánh mạnh session vừa collect. Có history file nhưng chưa dùng history để cập nhật trọng số theo thời gian.

Sau Phase 5.5 mới tiếp tục:

# Phase 6 — Initial Viewer / Viewer Robot Generator

### Tiến độ tương đối

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Schema / conventions | ~90% |
| 1 | 18 Level-1 Categories | 100% |
| 2 | Niche → Sub-niche → Topic → Subtopic | ~50% |
| 3 | Keyword Index | ~70% |
| 4 | Relationship Graph | ~30% |
| 5 | Video Content Classification | ~90% / MVP usable |
| 5.5 | Longitudinal Profile Evolution | 0% — **NEXT** |
| 6 | Initial Viewer Generator | 0% |
| 7 | Feed Simulation | 0% |
| 8 | Interaction Simulation | 0% |
| 9 | Interest Learning | ~20% concept/prior only |
| 10 | Behavior Archetypes | ~40% prototype từ exposure |
| 11 | Audience Clustering | 0% |
| 12 | Creator Strategy | ~60% prototype |
| 13 | Viewer ↔ Creator Matching | 0% |
| 14 | Closed Loop | 0% |
| 15 | Learned Transition Graph | ~20% foundation từ Up Next |
| 16 | Evaluation | ~20% coverage/separability foundation |

Các tỷ lệ chỉ là checkpoint kiến trúc, không phải benchmark.

---

## 3. Những gì đã làm được

### 3.1 Taxonomy + classifier

Có 18 internal Level-1 categories và classifier multi-label.

Đã tách rõ:

```text
CONTENT       = video thực sự nói về gì
INTENT        = video được trình bày theo kiểu gì
TARGET        = creator metadata/định vị hướng tới nhóm nào
POPULARITY    = demand/freshness proxy
EXPOSURE      = profile đang được hiển thị video đó ở surface nào
```

Classifier hiện có entity/anchor/support evidence, confidence, intent, target và popularity profile.

Không gọi coverage/separability là accuracy khi chưa có ground-truth labels.

### 3.2 YouTube Data API enrichment

Có thể enrich:

- description
- creator tags
- categoryId
- topicDetails
- publishedAt
- viewCount
- likeCount
- commentCount

API key chỉ đọc từ `YOUTUBE_API_KEY`.

### 3.3 Stable browser profile identity

Extension lưu riêng cho từng Chrome/Edge profile:

```text
profile_id
profile_label
profile_short_id
```

Nhiều browser profile không bị trộn dữ liệu.

### 3.4 Home collector

Read-only collector lấy:

```text
video_id
title
channel
position
```

Không click/play/like/comment/subscribe.

### 3.5 Up Next collector + replay

Flow:

```text
Home
  ↓
random vài seed video
  ↓
fetch watch-page HTML cùng browser profile
  ↓
parse secondaryResults
  ↓
Up Next replay nhiều lần
```

Replay dùng để đo stability, ví dụ:

```text
3/3 → stable hơn
1/3 → volatile / exploration hơn
```

### 3.6 Up Next video-only fix

Extension hiện là **0.4.1**.

Đã sửa lỗi 0.4.0 lấy nhầm Mix / playlist / “Danh sách kết hợp” từ `lockupViewModel/contentId`.

0.4.1:

- chỉ nhận video ID YouTube hợp lệ 11 ký tự;
- ưu tiên `watchEndpoint.videoId`;
- `lockupViewModel` chỉ nhận khi là video;
- playlist/radio/mix/collection bị loại;
- có `extraction_diagnostics`.

Cần tiếp tục validate trên vài profile thật.

### 3.7 Consolidated Profile Intelligence

Mỗi profile chỉ có một report current:

```text
data/profile_reports/profile_<id>__current.profile.json
data/profile_reports/profile_<id>__current.profile.html
```

Library:

```text
data/profile_library/index.json
data/profile_library/profile_<id>.json
data/profile_library/profile_<id>.history.jsonl
```

Profile hiện có:

- behavior profile name — nhãn nghiên cứu, không phải nhãn YouTube;
- certainty / uncertainty;
- interest weights;
- Home weight;
- Up Next weight;
- cross-surface support;
- core / adjacent / exploration;
- topic map;
- creative keywords;
- creator tags;
- stable Up Next;
- demand signal;
- opportunity score;
- content series plan;
- creative blueprints.

### 3.8 Surface weighting hiện tại

Trong **một collection session**, Home và Up Next không cộng 1:1:

```text
Home prior      ≈ 62%
Up Next context ≈ 38%
```

Up Next được normalize theo seed/replay để nhiều replay không áp đảo Home chỉ vì số observations lớn.

Quan trọng: đây là **intra-session weighting**, chưa phải longitudinal/time weighting.

### 3.9 Creator strategy prototype

Không đề xuất nhiều thể loại rời rạc.

```text
ANCHOR LANE            60–70%
BRIDGE LANE            20–30%
CONTROLLED EXPANSION   <=10–15%
```

Mở rộng phải giữ semantic continuity.

### 3.10 Creative brief / video blueprint

Consolidated profile hiện là `analysis_version 2.1.0` và có `creative_blueprints`.

Mỗi blueprint hướng dẫn:

```text
lane
profile fit
opportunity score

title guidance
- primary term
- supporting terms
- title examples

description guidance
- opening should state
- semantic terms nên phủ

tag guidance
- observed consistent tags
- supporting semantic tags

content blueprint
- format
- hook direction
- opening
- context/problem
- main value
- proof/example
- recap
- series bridge
- thumbnail direction
```

Creator tự quyết định nội dung thật, script, claim, ví dụ, footage, âm thanh, cách dựng và CTA.

---

## 4. Khoảng trống vừa xác định: profile chưa tiến hóa theo thời gian

Hiện `profile_<id>.history.jsonl` chỉ lưu snapshot lịch sử. `build_consolidated_profile.py` tính profile từ collection session hiện tại rồi overwrite current profile; chưa đọc history để tạo rolling/decayed state.

Do đó chưa có đúng nghĩa:

```text
Hôm qua profile thích gì
        +
Hôm nay đang được expose gì
        ↓
Hồ sơ mới sau khi cập nhật
```

Đây là mục tiêu của Phase 5.5.

---

# 5. Phase 5.5 — Longitudinal Profile Evolution

## 5.1 Mục tiêu

Mỗi browser profile trở thành một state sống, cập nhật định kỳ thay vì profile độc lập theo từng session.

Default cadence ban đầu:

```text
1 collection / profile / ngày
```

Cadence phải configurable; không coi 1 lần/ngày là quy luật của YouTube.

Một lần daily collection dự kiến đọc:

```text
HOME
+
UP NEXT replay
+
SUBSCRIPTIONS / subscribed-channel evidence
```

Sau đó update profile library current state.

## 5.2 Không trộn tất cả surface cùng một loại

Các evidence layer nên tách:

```text
recommendation_exposure
├── Home
└── Up Next

explicit_affinity
└── Subscriptions / subscribed channels

observed_behavior        # optional về sau
├── voluntarily captured search
├── watch history
├── click/watch/completion
└── other explicit behavior
```

**Subscriptions không phải recommendation surface.** Nó là explicit/long-term affinity evidence và phải có trọng số/layer riêng.

## 5.3 Profile temporal state đề xuất

Mỗi profile nên có:

```json
{
  "current": {},
  "rolling_1d": {},
  "rolling_7d": {},
  "rolling_30d": {},
  "long_term": {},
  "interest_trends": {},
  "profile_maturity": "new | forming | stable | drifting"
}
```

Mỗi category/topic/keyword có thể có:

```json
{
  "weight": 0.0,
  "previous_weight": 0.0,
  "delta_1d": 0.0,
  "delta_7d": 0.0,
  "trend": "emerging | rising | stable | cooling | dormant | revived",
  "first_seen": "...",
  "last_seen": "...",
  "persistence_days": 0,
  "surface_support": []
}
```

## 5.4 Time weighting

Không thay profile cũ hoàn toàn bằng snapshot mới.

Dùng decay/EMA configurable, ví dụ khái niệm:

```text
old_state × time_decay
+
new_daily_evidence × update_strength
↓
new_state
```

Có thể biểu diễn decay theo half-life:

```text
decay = exp(-ln(2) × age_days / half_life_days)
```

Half-life phải tune theo loại signal, không hard-code như “sự thật YouTube”.

Ví dụ logic ban đầu có thể phân biệt:

```text
Home exposure        → decay nhanh hơn
Up Next context      → decay nhanh hơn
Subscriptions        → decay chậm hơn
Repeated persistence → tăng confidence
```

## 5.5 Trọng số profile nên gồm nhiều tầng

Mỗi interest cuối không chỉ là category share.

Nên có:

```text
surface evidence
× position/confidence
× replay stability
× cross-surface support
× temporal decay
× multi-day persistence
× evidence quality
```

Không để một ngày bất thường làm profile pivot mạnh ngay lập tức.

## 5.6 Daily update output

Sau mỗi lần collect:

```text
1. lưu raw evidence
2. classify/enrich
3. build daily snapshot profile
4. đọc historical state
5. temporal update
6. ghi current profile
7. append history
8. render current HTML
```

HTML nên thêm:

```text
TODAY
7-DAY TREND
30-DAY CORE
RISING INTERESTS
COOLING INTERESTS
NEWLY EMERGING TOPICS
PERSISTENT KEYWORDS/TAGS
SUBSCRIBED CHANNEL AFFINITY
PROFILE MATURITY
```

## 5.7 Subscriptions surface

Cần thêm collector read-only cho ít nhất:

```text
subscribed channel list
subscription feed / latest subscribed videos
```

Nên aggregate:

```text
channel affinity
channel topic vector
category/topic distribution
recency of subscribed uploads
```

Không tự subscribe/unsubscribe.

## 5.8 Profile naming theo thời gian

Tên hồ sơ hiện tại không nên đổi chỉ vì một snapshot.

Đề xuất:

```text
candidate_name
→ phải persist N ngày / đủ confidence
→ mới promote thành behavior_profile_name
```

Có thể lưu:

```text
current_name
candidate_name
candidate_confidence
name_stability_days
previous_names
```

---

## 6. Những signal nên bổ sung sau Home + Up Next + Subscriptions

Không nhất thiết làm tất cả ngay. Thứ tự ưu tiên:

### A. Channel affinity — ưu tiên cao

Không chỉ category/topic, cần biết profile thường được expose những channel nào.

```text
channel repeated on Home
+
channel repeated in Up Next
+
subscribed channel
↓
channel affinity
```

Creator strategy có thể dùng channel-neighborhood như evidence phụ.

### B. Freshness preference — ưu tiên cao

Profile có thiên về:

```text
breaking / same-day
recent <7d
evergreen
old catalog
```

Điều này ảnh hưởng loại video creator nên làm.

### C. Format preference — ưu tiên cao

Tách preference:

```text
long-form
short-form
livestream
playlist/compilation
tutorial
analysis/review
news
```

Duration hiện cần extractor tốt hơn để dùng đáng tin cậy.

### D. Language / locale profile

Theo dõi ngôn ngữ nội dung đang được expose:

```text
Vietnamese
English
Korean
Turkish
...
```

Không suy ra dân tộc/quốc tịch; chỉ mô tả language exposure.

### E. Time-of-day / day-of-week segments

Nếu sau này collect nhiều lần/ngày:

```text
morning profile
night profile
weekday
weekend
```

Một profile có thể có interest context khác nhau theo thời điểm.

### F. Baseline / control exposure — rất đáng làm

Có một profile mới hoặc neutral/control snapshot để ước lượng:

```text
profile exposure
-
global/common exposure baseline
=
profile-specific signal proxy
```

Giúp tránh hiểu nhầm một trend toàn YouTube là sở thích riêng của profile.

### G. Optional observed behavior evidence

Chỉ nếu người dùng chủ động muốn dùng dữ liệu read-only:

```text
watch history
search queries/results đã tự thực hiện
liked/watch-later playlists
```

Các signal này phải lưu riêng khỏi recommendation exposure và mạnh hơn prior khi update posterior.

Không tự tạo hành vi thật.

### H. Transition persistence

Up Next không chỉ đo video ổn định mà còn đo:

```text
Topic A → Topic B
Topic B → Topic C
```

Nếu transition tồn tại nhiều ngày, nó là bridge lane tốt hơn một transition chỉ xuất hiện một session.

### I. Exposure saturation / novelty

Creator strategy nên biết một vùng nội dung:

```text
đang tăng
đang ổn định
đã bão hòa trong profile observations
```

Không chỉ chọn topic có trọng số cao nhất.

### J. Evidence provenance

Mỗi trọng số nên truy được:

```text
vì Home ngày nào
vì Up Next seed nào
vì subscription/channel nào
vì keyword/topic nào
```

Để debug và giải thích được profile.

---

## 7. Các module quan trọng hiện tại

```text
browser_extension/youtube_home_collector/
  manifest.json
  popup.html
  popup.js

scripts/homepage/home_bridge.py
scripts/enrichment/youtube_enrich.py
scripts/classification/classify_homepage_v2.py
scripts/profile/build_profile_report.py
scripts/profile/build_consolidated_profile.py

taxonomy/content_rules.v2.json
taxonomy/homepage_categories.v1.json

docs/PROFILE_INTELLIGENCE_MODEL.md
PROJECT_PLAN.md
PLAN.md
```

Checkpoint đáng nhớ:

```text
7df991b  extension 0.4.1 — Up Next video-only fix
93f3ba8  consolidated profile 2.1 — creative title/description/tag blueprint
```

Luôn fetch file hiện tại từ GitHub trước khi sửa.

---

## 8. Những phần vẫn còn chưa làm

### Taxonomy sâu

Chưa hoàn thiện toàn bộ:

```text
Category → Niche → Sub-niche → Topic → Subtopic
```

### Classifier v3

Sau khi có đủ validation data:

- direct topicDetails → internal taxonomy mapping;
- giảm weight broad official category IDs;
- tag-content consistency mạnh hơn;
- contextual AI;
- intent fixes;
- entities/anchors;
- unit tests.

### Transition Graph chính thức

Up Next mới là foundation, chưa có graph learned/persistent đầy đủ.

### Cross-profile overlap / clustering

Chưa làm.

### Channel DNA / Candidate Scoring

Chưa có module nhập idea mới và chấm đầy đủ:

```text
Profile fit
Channel DNA fit
Home overlap
Up Next overlap
Subscription/channel affinity
Keyword overlap
Demand
Freshness
Series continuity
Temporal trend
```

### API metadata cache

Chưa có cache theo `video_id` để tránh enrich lặp.

### Automatic daily scheduler

Chưa có scheduler chính thức.

Mục tiêu sau khi Phase 5.5 engine ổn:

```text
1 profile → mặc định 1 daily collection
```

Có thể dùng local scheduler/browser extension timer về sau, nhưng collector vẫn phải read-only và giữ browser profile identity.

---

## 9. Definition of Done — Phase 5.5

Phase 5.5 hoàn thành khi:

- current profile không bị thay hoàn toàn bởi một snapshot mới;
- có daily/rolling/long-term weights;
- có configurable time decay;
- có emerging/rising/stable/cooling state;
- có profile maturity;
- Home và Up Next vẫn giữ vai trò khác nhau;
- Subscriptions được thu read-only và giữ thành explicit affinity layer;
- current report cho thấy hôm nay thay đổi gì so với 7/30 ngày;
- profile naming có stability/hysteresis;
- evidence provenance truy được;
- historical state có thể dùng làm `observed_profile_prior` cho Phase 6.

---

# 10. Sau Phase 5.5 — Phase 6 Viewer Robot

Viewer synthetic/offline nên hỗ trợ hai seed mode:

```text
pure synthetic
observed-profile-prior seeded
```

Observed profile prior lúc này sẽ tốt hơn vì đã được tích lũy nhiều ngày thay vì chỉ dựa vào một session.

Sau Phase 6:

```text
Phase 7  Feed Simulation
Phase 8  Interaction Simulation
Phase 9  Interest Learning
Phase 10 Behavior Archetypes từ simulation history
Phase 11 Audience Clustering
Phase 12 Creator Strategy hoàn thiện
Phase 13 Viewer ↔ Creator Matching
Phase 14 Closed Loop
Phase 15 Learned Transition Graph
Phase 16 Evaluation
```

---

## 11. Gợi ý mở cuộc trò chuyện tiếp theo

> Đọc `PLAN.md` và tiếp tục Phase 5.5 — Longitudinal Profile Evolution. Trước tiên thiết kế temporal profile schema, daily update/decay engine và Subscriptions read-only surface; chưa sang Viewer Robot cho tới khi historical profile state hoạt động.

---

## 12. Nguyên tắc an toàn / phạm vi

- Collector thật chỉ read-only.
- Không click/play/like/comment/subscribe tự động.
- Không tạo fake traffic/view/engagement.
- Recommendation exposure không được gọi là watch behavior thật.
- Subscriptions là explicit affinity, không được trộn như Home recommendation.
- Optional watch/search/history evidence phải tách riêng khỏi exposure.
- Creator opportunity score là heuristic nghiên cứu, không đảm bảo impressions/views.
- Official YouTube metadata chỉ là evidence/reference, không phải semantic ground truth.
