# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> Đây là checkpoint canonical để tiếp tục dự án. Roadmap gốc vẫn ở `PROJECT_PLAN.md`.

# 1. Mục tiêu hệ thống đã chốt

`youtube_library` có ba population phải tách biệt:

```text
A. OBSERVED PROJECT PROFILES
   browser profiles được theo dõi read-only
   → Home / Up Next / Subscriptions / longitudinal state

B. SYNTHETIC VIEWER ROBOTS
   viewer mô phỏng hoàn toàn offline
   → feed simulation / interaction / interest learning

C. EXTERNAL REAL AUDIENCE
   người xem thật ngoài dự án
   → không kiểm soát
```

Creator-facing mục tiêu cuối là:

```text
Observed profile panel
+
Synthetic audience model
+
Creator content candidate
↓
Audience-fit / cohort-coverage estimate
↓
Creator chọn nội dung để xuất bản organically
↓
External real audience phản hồi tự nhiên
↓
Optional creator-owned analytics để calibrate model
```

Không dùng observed project profiles hoặc synthetic robots để tạo view/click/like/comment/subscription thật.

---

# 2. Trạng thái roadmap hiện tại

```text
Phase 5   Video Content Classification        MVP usable
Phase 5.5 Longitudinal Profile Evolution      core implemented, validation continues
Phase 6   Initial Viewer / Viewer Robot        ACTIVE — MVP slice 1 implemented
Phase 7   Offline Feed Simulation              next after Phase 6 validation
Phase 8   Synthetic Interaction Simulation     pending
Phase 9   Interest Learning                    pending
```

Phase 5.5 không còn chặn việc code Phase 6. Daily profile validation 3–7 ngày có thể tiếp tục song song.

---

# 3. Phase 5.5 checkpoint

Current observed profile pipeline:

```text
Home
+
Up Next replay
+
Subscriptions read-only
↓
API enrichment
↓
classifier
↓
session profile
↓
daily observation
↓
Today / 7d / 30d / Long-term decay
↓
trend states
↓
current longitudinal profile
```

Current extension / bridge:

```text
extension 0.5.0
bridge 0.8
temporal profile analysis 2.5.0
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

Observed profile current state:

```text
data/profile_library/profile_<id>.json
```

Daily observations:

```text
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
```

Phase 5.5 validation vẫn cần kiểm tra trên dữ liệu thật nhiều ngày, nhưng không thêm feature lớn trừ bug rõ ràng.

---

# 4. Phase 6 — Viewer Robot: mục tiêu

Viewer Robot là **offline synthetic entity**.

Một robot ban đầu cần có:

```text
category interest vector
primary interests
secondary/adjacent interests
low/background interests
exploration interests
intent preferences
exploration rate
novelty tolerance
diversity preference
stability preference
simulation state
reproducible random lineage
```

Không random 18 category độc lập/đều nhau.

Structured generation:

```text
primary content family
↓
relationship graph
↓
adjacent interests
↓
small exploration/background interests
↓
normalized viewer vector
```

---

# 5. Phase 6 seed modes

## 5.1 Pure synthetic

```text
18-category taxonomy
+
seed interest relationship graph
+
master random seed
↓
synthetic cohort
```

Dùng để tạo population không phụ thuộc browser profile thật.

## 5.2 Observed-profile-prior seeded

```text
longitudinal profile_library/profile_<id>.json
+
controlled perturbation
+
adjacent exploration graph
+
master random seed
↓
synthetic cohort quanh observed profile prior
```

Không copy profile thật 1:1.

Concept:

```text
1 observed profile
↓
100–1000 synthetic viewers tương tự nhưng không giống hệt nhau
↓
Phase 7/8 offline testing
```

Robots không có cookie/account/browser credential và không có code hành động trên YouTube.

---

# 6. Phase 6 slice 1 — IMPLEMENTED

## 6.1 Viewer schema

```text
schemas/viewer_robot.v1.schema.json
```

Core object:

```json
{
  "viewer_id": "viewer-...",
  "seed_source": "pure_synthetic | observed_profile_prior",
  "random_seed": 0,
  "lineage": {},
  "interest_model": {
    "category_vector": {},
    "primary_interests": [],
    "secondary_interests": [],
    "low_interests": [],
    "exploration_interests": [],
    "topic_vector": {}
  },
  "preference_model": {
    "exploration_rate": 0.0,
    "novelty_tolerance": 0.0,
    "diversity_preference": 0.0,
    "stability_preference": 0.0,
    "intent_preferences": {}
  },
  "simulation_state": {
    "step": 0,
    "interaction_count": 0,
    "last_video_id": null,
    "state_version": 0
  }
}
```

`simulation_state` chỉ được khởi tạo ở Phase 6; chưa update cho tới Phase 8/9.

## 6.2 Seed relationship graph

```text
taxonomy/interest_relations.v1.json
```

Seed relations gồm các hướng như:

```text
Technology ↔ Education
Technology ↔ Business
Gaming ↔ Entertainment
Sports ↔ Health
Food ↔ Travel
Entertainment ↔ Music
People/Lifestyle ↔ How-to
Society ↔ News
```

Weights là research prior của project, không phải thống kê recommendation YouTube.

## 6.3 Generator

```text
scripts/viewer/generate_viewers.py
```

Supports:

```text
pure_synthetic
observed_profile_prior
```

Output:

```text
data/synthetic_viewers/<batch_id>/
  manifest.json
  viewers.jsonl
```

Generated viewer cohorts được `.gitignore` mặc định vì observed-prior cohorts có thể kế thừa personalized research priors.

## 6.4 Reproducibility

Viewer ID + viewer random seed + model fields được derive deterministic từ:

```text
master seed
+
seed mode
+
source profile token nếu có
+
viewer index
```

Same inputs/master seed → same model state.
`created_at` có thể khác giữa các lần chạy.

## 6.5 Cohort summary

```text
scripts/viewer/summarize_viewer_batch.py
```

Summary kiểm tra:

```text
viewer count
seed source distribution
mean category vector
primary category counts
exploration category counts
mean exploration/novelty/diversity/stability
co-interest pairs >= 5% weight
```

Mục tiêu là phát hiện generator quá đồng nhất hoặc sinh population vô lý trước Phase 7.

## 6.6 Tests/docs

```text
tests/test_viewer_generator.py
docs/VIEWER_ROBOT_MODEL.md
.github/workflows/python-tests.yml
```

Tests cover:

```text
normalized category vector
structured pure-synthetic generation
same-seed reproducibility
different viewer-index variability
observed-profile-prior direction preservation
batch uniqueness/count
```

---

# 7. Cách chạy Phase 6 hiện tại

## 7.1 Pure synthetic cohort

```bat
python scripts\viewer\generate_viewers.py --mode pure_synthetic --count 1000 --seed 42
```

Force một primary family nếu cần test cohort chuyên biệt:

```bat
python scripts\viewer\generate_viewers.py --mode pure_synthetic --count 500 --seed 42 --primary gaming
```

## 7.2 Seed từ observed longitudinal profile

```bat
python scripts\viewer\generate_viewers.py ^
  --mode observed_profile_prior ^
  --profile data\profile_library\profile_<id>.json ^
  --count 500 ^
  --seed 42
```

## 7.3 Inspect cohort

```bat
python scripts\viewer\summarize_viewer_batch.py data\synthetic_viewers\<batch_id>\viewers.jsonl
```

Output thêm:

```text
summary.json
```

---

# 8. Phase 6.2 — việc tiếp theo cần làm

Sau slice 1, chưa sang Feed Simulation ngay cho tới khi kiểm tra cohort.

## 8.1 Generator validation

Chạy ít nhất:

```text
10,000 pure synthetic viewers
500–1000 viewers quanh mỗi observed profile usable
```

Kiểm tra:

```text
primary distribution có quá lệch không
secondary có thực sự theo adjacency graph không
exploration có quá nhiều/ít không
observed cohort có giữ đúng content neighborhood không
certainty thấp có tạo variance cao hơn certainty cao không
same seed có reproducible không
```

## 8.2 Population composition

Hiện một batch chỉ có một seed mode/source profile.

Phase 6.2 nên thêm population builder:

```text
pure synthetic cohorts
+
multiple observed-profile seeded cohorts
↓
one simulation population manifest
```

Ví dụ:

```text
10,000 viewers
├── 4,000 broad pure synthetic
├── 1,000 around observed Profile A
├── 1,000 around observed Profile B
├── 1,000 around observed Profile C
└── 3,000 stratified primary-category cohorts
```

Không coi tỷ lệ trên là population thật của YouTube; đây là simulation experiment composition.

## 8.3 Profile uncertainty propagation

Observed profile certainty phải ảnh hưởng variance synthetic:

```text
certainty cao
→ robots gần prior hơn

certainty thấp
→ robots phân tán hơn / exploration cao hơn
```

Slice 1 đã có logic nền; cần validate bằng summary/stat tests.

## 8.4 Topic-level detail

Phase 6 MVP dùng Category mạnh nhất và optional `topic_vector` từ observed profile.

Không chặn Phase 7 vì taxonomy sâu chưa hoàn chỉnh.

Sau này khi Phase 2/3 sâu hơn, Viewer Robot có thể nâng:

```text
Category
→ Niche
→ Topic
→ Subtopic
```

mà không đổi viewer_id contract lớn.

---

# 9. Definition of Done — Phase 6

Phase 6 hoàn thành khi:

- schema Viewer Robot ổn định cho Phase 7;
- pure synthetic mode hoạt động;
- observed-profile-prior mode hoạt động;
- relationship-based secondary interests hoạt động;
- same seed reproducible;
- cohort summary/validation không cho thấy bias lỗi rõ ràng;
- population builder có thể kết hợp nhiều cohort;
- generated data chỉ offline/local;
- tests pass;
- không có code nào gửi Viewer Robot lên YouTube hoặc tạo real interaction.

---

# 10. Phase 7 — thiết kế ngay sau Phase 6

Input:

```text
Viewer Robot
+
Video Content Vector
+
optional context/relationship features
```

Output:

```text
ranked synthetic feed
```

Initial transparent score dự kiến:

```text
viewer-content similarity
+
intent fit
+
transition/adjacency fit
+
novelty/exploration
+
freshness/demand proxy
```

Mỗi component phải lưu riêng để giải thích được tại sao video được rank.

Phase 7 không truy cập YouTube và không tạo interaction thật.

---

# 11. Phase 8–9 preview

## Phase 8 — Synthetic Interaction

Robot có thể offline sinh event như:

```text
skip
short_watch
medium_watch
long_watch
completion
rewatch
synthetic_like_signal
synthetic_interest_signal
```

Các event chỉ nằm trong local simulation logs, không map thành action thật trên YouTube.

## Phase 9 — Interest Learning

```text
old interest vector
+
synthetic interaction evidence
+
time decay
↓
new synthetic viewer state
```

Khi đó mới bắt đầu hình thành behavioral history thật của Viewer Robot.

---

# 12. Creator-facing direction vẫn giữ nguyên

Người sáng tạo cuối cùng không cần xem từng robot.

Robots là backend model để sau này tính:

```text
candidate video
↓
match synthetic population
↓
cohort coverage
↓
match observed project profiles
↓
creator opportunity summary
```

Creator Dashboard mặc định cần trả:

```text
tracked observed profiles
usable profiles
synthetic cohort size
content lane coverage
rising/stable opportunity breadth
recommended anchor / bridge / expansion
keyword/title/description/tag guidance
creative blueprint
certainty/limitations
```

Không gọi cohort coverage là probability of view/recommendation.

---

# 13. Important current modules

```text
# observed profile side
browser_extension/youtube_home_collector/
scripts/homepage/home_bridge.py
scripts/profile/build_consolidated_profile.py
scripts/profile/build_temporal_profile.py

# Phase 6 synthetic side
schemas/viewer_robot.v1.schema.json
taxonomy/interest_relations.v1.json
scripts/viewer/generate_viewers.py
scripts/viewer/summarize_viewer_batch.py
docs/VIEWER_ROBOT_MODEL.md
tests/test_viewer_generator.py
```

---

# 14. Phase 5.5 validation continues in parallel

Vẫn collect observed project profiles khoảng 1 lần/ngày khi thuận tiện.

Không cần dừng Phase 6 để chờ đủ 7 ngày.

Observed data tốt hơn theo thời gian sẽ tạo seed prior tốt hơn cho generator.

---

# 15. Next action for the next conversation

Tiếp tục Phase 6:

> Đọc `PLAN.md`. Phase 6 Viewer Robot slice 1 đã implemented. Tiếp tục Phase 6.2: validate cohort generator, thêm multi-cohort population builder và chuẩn bị contract input/output cho Phase 7 Feed Simulation.

Nếu Phase 6 validation đã ổn:

> Đọc `PLAN.md` và bắt đầu Phase 7 — Offline Feed Simulation. Feed score phải decomposable và chỉ chạy trên synthetic/local data.

---

# 16. Safety / scope bắt buộc

- Observed collector thật chỉ read-only.
- Không tự click/play/like/comment/subscribe/unsubscribe trên YouTube thật.
- Không fake traffic/view/engagement.
- Không dùng observed project profiles làm nhóm tạo initial engagement.
- Viewer Robot chỉ synthetic/offline.
- Synthetic interaction chỉ ghi local simulation logs.
- External real audience là population ngoài dự án.
- Audience-fit/cohort coverage không phải xác suất view/recommendation.
- Creator opportunity score là heuristic nghiên cứu.
- Official YouTube metadata là evidence/reference, không phải semantic ground truth.
