# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> File này là **checkpoint ngắn gọn để tiếp tục dự án ở các cuộc trò chuyện sau**. Roadmap đầy đủ ban đầu vẫn nằm trong `PROJECT_PLAN.md`. Khi bắt đầu phiên mới, đọc `PLAN.md` trước rồi tham chiếu `PROJECT_PLAN.md` khi cần chi tiết.

## 1. Mục tiêu dự án đã chốt

`youtube_library` hướng tới một hệ thống nghiên cứu/offline gồm hai phía:

1. **Viewer side** — mô tả và mô phỏng hồ sơ người xem, sở thích, hành vi và sự thay đổi theo thời gian.
2. **Creator side** — dùng các hồ sơ/cluster đã quan sát hoặc mô phỏng để đề xuất chuỗi nội dung mới có semantic fit tốt với các vùng recommendation đang quan sát.

Mục tiêu không phải sao chép chính xác taxonomy hay recommendation nội bộ của YouTube. Taxonomy của dự án là công cụ nghiên cứu riêng, tối ưu cho việc:

- hiểu profile đang được expose nội dung gì;
- xác định core / adjacent / exploration interests;
- tìm keyword / creator tags / topic neighborhood;
- xây hướng nội dung mới theo chuỗi, không pivot lung tung;
- về sau mô phỏng Viewer Robot và closed-loop offline.

Không dùng robot để tạo traffic, view, click, like, comment hoặc tương tác giả trên YouTube thật.

---

## 2. Trạng thái hiện tại

### Milestone hiện tại

**Recommendation Profile Intelligence MVP**

Theo roadmap gốc, dự án đang ở **cuối Phase 5 — Video Content Classification**, đã prototype trước một phần của Phase 10 và Phase 12. Bước tiếp theo chính thức sau khi validate phần hiện tại là **Phase 6 — Initial Viewer / Viewer Robot Generator**.

### Tiến độ tương đối

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Schema / conventions | ~90% |
| 1 | 18 Level-1 Categories | 100% |
| 2 | Niche → Sub-niche → Topic → Subtopic | ~50% |
| 3 | Keyword Index | ~70% |
| 4 | Relationship Graph | ~30% |
| 5 | Video Content Classification | ~90% / MVP usable |
| 6 | Initial Viewer Generator | 0% — **NEXT** |
| 7 | Feed Simulation | 0% |
| 8 | Interaction Simulation | 0% |
| 9 | Interest Learning | ~20% concept/prior only |
| 10 | Behavior Archetypes | ~40% prototype từ recommendation exposure |
| 11 | Audience Clustering | 0% |
| 12 | Creator Strategy | ~60% prototype |
| 13 | Viewer ↔ Creator Matching | 0% |
| 14 | Closed Loop | 0% |
| 15 | Learned Transition Graph | ~20% foundation từ Up Next |
| 16 | Evaluation | ~20% coverage/separability foundation |

Các tỷ lệ trên là checkpoint kiến trúc, không phải metric benchmark chính thức.

---

## 3. Những gì đã làm được

### 3.1 Taxonomy và classifier

Internal Level-1 taxonomy có 18 Category:

1. Entertainment
2. News & Politics
3. Music
4. Gaming
5. Sports
6. Film & Animation
7. Education
8. Science & Technology
9. People & Lifestyle
10. How-to & Style
11. Travel & Events
12. Autos & Vehicles
13. Pets & Animals
14. Comedy
15. Society & Community
16. Business & Finance
17. Health & Fitness
18. Food & Cooking

Đã tách các lớp:

```text
CONTENT       = video thực sự nói về gì
INTENT        = video được trình bày theo kiểu gì
TARGET        = metadata/định vị creator đang hướng tới nhóm nào
POPULARITY    = demand/freshness proxy
EXPOSURE      = YouTube đang hiển thị video đó cho profile ở surface nào
```

Classifier hiện hỗ trợ multi-label, entity/anchor/support evidence, confidence, intent, target và popularity profile.

Metrics không có ground truth phải gọi là **coverage / separability**, không gọi là accuracy.

### 3.2 YouTube Data API enrichment

Pipeline có thể enrich video bằng:

- description
- creator tags
- YouTube categoryId
- topicDetails
- publishedAt
- viewCount
- likeCount
- commentCount

API key chỉ đọc từ environment (`YOUTUBE_API_KEY`), không lưu trong repo.

### 3.3 Browser profile identity

Mỗi Chrome/Edge browser profile có stable ID riêng được extension lưu trong `chrome.storage.local`:

```text
profile_id
profile_label
profile_short_id
```

Nhờ đó dữ liệu nhiều browser profile không bị trộn.

### 3.4 Home collector

Extension đọc YouTube Home theo chế độ read-only:

- scroll
- đọc cards
- video_id
- title
- channel
- position

Không click/play/like/comment/subscribe.

### 3.5 Up Next collector + replay

Flow hiện tại:

```text
Home
  ↓
random vài video seed
  ↓
fetch watch-page HTML cùng browser profile
  ↓
parse secondaryResults
  ↓
Up Next replay nhiều lần
```

Mục tiêu replay là đo stability:

```text
video xuất hiện 3/3 → ổn định hơn
video xuất hiện 1/3 → volatile / exploration hơn
```

Các replay chỉ là evidence nội bộ, không tạo hàng loạt report người dùng.

### 3.6 Fix Up Next quan trọng

Extension `0.4.0` từng lấy nhầm `lockupViewModel/contentId`, dẫn đến Mix / playlist / “Danh sách kết hợp” bị coi là video.

Đã sửa ở extension **0.4.1**:

- chỉ nhận video ID YouTube hợp lệ 11 ký tự;
- ưu tiên `watchEndpoint.videoId`;
- `lockupViewModel` chỉ được nhận nếu là video;
- playlist / radio / mix / collection bị loại;
- snapshot có `extraction_diagnostics`.

**Việc cần validate ngắn hạn:** chạy thử 0.4.1 trên vài profile để xác nhận Up Next chỉ còn video đơn.

### 3.7 Consolidated Profile Intelligence

Raw Home / Up Next vẫn lưu riêng làm evidence, nhưng mỗi browser profile chỉ có **một current profile report tổng hợp**.

Output chính:

```text
data/profile_reports/profile_<id>__current.profile.json
data/profile_reports/profile_<id>__current.profile.html
```

Profile library:

```text
data/profile_library/index.json
data/profile_library/profile_<id>.json
data/profile_library/profile_<id>.history.jsonl
```

Hồ sơ tổng hợp gồm:

- behavior profile name (nhãn nghiên cứu, không phải nhãn YouTube)
- certainty / uncertainty
- interest weights
- Home weight
- Up Next weight
- cross-surface support
- core / adjacent / exploration
- topic map
- creative keywords
- creator tags
- stable Up Next videos
- opportunity score
- content series plan

### 3.8 Surface weighting đã chốt

Home và Up Next không được cộng 1:1.

Khởi đầu hiện tại:

```text
Home prior      ≈ 62%
Up Next context ≈ 38%
```

Up Next replay được normalize theo seed/replay để 3 seed × 5 replay không vô tình áp đảo Home chỉ vì nhiều observations hơn.

### 3.9 Creator strategy prototype

Không đề xuất creator làm nhiều thể loại rời rạc chỉ vì profile có nhiều interest.

Chiến lược hiện tại:

```text
ANCHOR LANE              60–70%
BRIDGE LANE              20–30%
CONTROLLED EXPANSION     <=10–15%
```

Mở rộng phải có semantic continuity và evidence từ Home / Up Next / replay stability.

### 3.10 Creative brief / video blueprint

Profile report hiện có `creative_blueprints` cho từng lane.

Hệ thống chỉ hướng dẫn, không viết hộ video hoàn chỉnh.

Mỗi blueprint có:

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
- terms nên phủ tự nhiên

tag guidance
- observed consistent tags
- supporting semantic tags

content blueprint
- recommended format
- hook direction
- opening
- context/problem
- main value
- proof/example
- recap
- series bridge
- thumbnail direction
```

Creator vẫn phải tự quyết:

- góc nhìn / luận điểm
- kịch bản / lời thoại
- ví dụ / bằng chứng
- footage / hình ảnh / âm thanh
- nhịp dựng
- storytelling
- claim
- CTA

Nguyên tắc keyword/title/tag:

- title chỉ cần 1 primary term + tối đa 1–2 supporting terms tự nhiên;
- description nên phủ semantic terms thật sự liên quan, không keyword stuffing;
- tags chỉ dùng khi đúng nội dung thật;
- tags/keywords là metadata/semantic guidance, không được coi là nút điều khiển recommendation.

---

## 4. Các module quan trọng hiện tại

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

Các commit checkpoint gần nhất đáng nhớ:

```text
7df991b  extension 0.4.1 — Up Next video-only fix
93f3ba8  consolidated profile 2.1 — creative title/description/tag blueprint
```

Luôn fetch file hiện tại từ GitHub trước khi sửa; không overwrite từ SHA cũ trong hội thoại.

---

## 5. Những quyết định kiến trúc đã chốt

### 5.1 Profile hiện tại là recommendation exposure profile

Không được tuyên bố Home/Up Next cho biết watch history thật.

Hiện tại profile là:

```text
Recommendation Prior / Exposure Profile
```

Sau này khi có synthetic behavior hoặc observational behavior evidence mới cập nhật thành posterior mạnh hơn.

### 5.2 Profile mới vẫn có prior

Ngay cả browser profile mới, Home vẫn đưa ra một tập nội dung ban đầu. Dự án dùng chính exposure đó làm prior mơ hồ ban đầu rồi dần giảm uncertainty bằng nhiều snapshot/surface/evidence.

### 5.3 Up Next là contextual neighborhood

Home trả lời gần với:

> Profile này đang được expose những vùng nội dung nào?

Up Next trả lời gần với:

> Từ một seed cụ thể, recommendation neighborhood đang mở sang đâu?

Không được coi hai surface là cùng một loại evidence.

### 5.4 Raw evidence và report người dùng tách nhau

- raw Home / Up Next / replay: lưu riêng để audit/debug;
- current profile report: một JSON + một HTML duy nhất trên mỗi profile;
- history: dùng cho drift / maturity về sau.

### 5.5 Taxonomy nội bộ không cần giống YouTube

Official category/topic là evidence/reference, không phải ground truth.

Mục tiêu taxonomy là hữu ích cho:

```text
classification
→ profile understanding
→ content continuity
→ creator opportunity
→ simulation
```

### 5.6 Kênh creator phải có Content DNA

Không tối ưu video độc lập cho mọi interest của profile.

Mỗi channel sau này cần có:

```text
core content DNA
allowed adjacent lanes
controlled expansion boundaries
```

Mỗi video candidate nên được chấm cả:

```text
profile fit
+
channel DNA fit
+
series continuity
```

---

## 6. Những phần chưa làm / cần quay lại

### Taxonomy sâu

Chưa hoàn thiện toàn bộ:

```text
Category
→ Niche
→ Sub-niche
→ Topic
→ Subtopic
```

cho cả 18 Category.

### Topic normalization / classifier v3

Vẫn nên làm sau khi validation đủ dữ liệu:

- direct topicDetails → internal taxonomy mapping;
- giảm weight official broad category IDs;
- tag-content consistency mạnh hơn;
- contextual AI handling;
- intent fixes;
- thêm entities/anchors;
- synthetic/public unit tests.

### Transition Graph

Chưa có graph chính thức. Dữ liệu Up Next hiện đã đủ làm nền cho:

```text
A → B
B → C
```

và sau này `appearance_rate`, `mean_position`, transition support.

### Cross-profile overlap

Chưa làm clustering / overlap giữa nhiều profile.

### Channel DNA / Candidate Scoring

Chưa có module riêng để nhập một idea mới và chấm:

```text
Profile fit
Channel DNA fit
Home overlap
Up Next overlap
Keyword overlap
Demand
Freshness
Series continuity
```

### API cache

Chưa cache metadata theo video_id. Cần làm về sau để tránh gọi API lại cho video trùng qua nhiều replay/session.

---

## 7. Bước tiếp theo chính thức

Sau khi test nhanh extension 0.4.1 và consolidated report 2.1 ổn trên vài browser profile, **không tiếp tục nhồi thêm feature vào Profile Intelligence**.

Bước tiếp theo theo roadmap là:

# Phase 6 — Initial Viewer / Viewer Robot Generator

Mục tiêu: sinh viewer synthetic/offline có prior có cấu trúc.

Viewer ban đầu cần có tối thiểu:

```json
{
  "viewer_id": "...",
  "seed_source": "synthetic | observed_profile_prior",
  "primary_interests": [],
  "secondary_interests": [],
  "low_interests": [],
  "topic_vector": {},
  "intent_preferences": {},
  "exploration_rate": 0.1,
  "novelty_tolerance": 0.2,
  "random_seed": 0
}
```

Hai chế độ nên hỗ trợ ngay từ đầu:

1. **Pure synthetic** — sinh từ taxonomy + relationship seed graph.
2. **Observed-prior seeded** — dùng current `profile_library/profile_<id>.json` làm prior khởi tạo robot, nhưng robot vẫn hoạt động hoàn toàn offline.

### Definition of Done cho Phase 6

- sinh được nhiều robot khác nhau nhưng có cấu trúc;
- reproducible bằng `random_seed`;
- một robot có primary + adjacent + exploration interests;
- không random mọi category độc lập/đều nhau;
- có thể seed robot từ một recommendation exposure profile đã quan sát;
- output validate được và dùng trực tiếp cho Phase 7 Feed Simulation.

### Sau Phase 6

```text
Phase 7  Feed Simulation
Phase 8  Interaction Simulation
Phase 9  Interest Learning
Phase 10 Behavior Archetypes từ history thật của simulation
Phase 11 Audience Clustering
Phase 12 Creator Strategy hoàn thiện
Phase 13 Viewer ↔ Creator Matching
Phase 14 Closed Loop
Phase 15 Learned Transition Graph
Phase 16 Evaluation
```

---

## 8. Gợi ý bắt đầu cuộc trò chuyện tiếp theo

Có thể mở bằng câu:

> Đọc `PLAN.md` và tiếp tục từ Phase 6 — Initial Viewer / Viewer Robot Generator. Trước tiên thiết kế schema viewer và generator hỗ trợ cả pure synthetic lẫn observed-profile-prior.

Hoặc nếu muốn validate checkpoint hiện tại trước:

> Đọc `PLAN.md`, kiểm tra extension 0.4.1 + consolidated profile 2.1 trên dữ liệu mới, sau đó mới bắt đầu Phase 6.

---

## 9. Nguyên tắc an toàn / phạm vi bắt buộc

- Collector thật chỉ được read-only.
- Không click/play/like/comment/subscribe tự động trên YouTube thật.
- Không tạo fake views/traffic/engagement.
- Viewer Robot từ Phase 6 trở đi phải chạy synthetic/offline.
- Creator opportunity score là heuristic nghiên cứu, không đảm bảo impressions/views.
- Không gọi official YouTube category/topic/tag là ground truth cho semantic nội dung.
- Không gọi coverage/separability là accuracy nếu chưa có labeled ground truth.
