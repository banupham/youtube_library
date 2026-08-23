# /plan — YouTube Library continuation checkpoint

> Cập nhật: 2026-08-23
>
> Đây là checkpoint canonical để tiếp tục dự án ở các cuộc trò chuyện sau. Roadmap gốc đầy đủ vẫn ở `PROJECT_PLAN.md`.

## 1. Mục tiêu đã chốt

`youtube_library` là hệ thống nghiên cứu/offline gồm hai phía:

1. **Viewer side** — quan sát recommendation exposure của browser profile thật theo chế độ read-only, xây profile theo thời gian, sau đó mô phỏng viewer synthetic/offline.
2. **Creator side** — dùng profile/cluster để đề xuất chuỗi nội dung mới có semantic fit tốt với vùng recommendation đang quan sát.

Taxonomy nội bộ không cần giống chính xác YouTube. Nó được tối ưu cho:

```text
classification
→ profile understanding
→ profile evolution
→ content continuity
→ creator opportunity
→ viewer simulation
```

Không dùng robot để tạo traffic, view, click, like, comment, subscribe hoặc tương tác giả trên YouTube thật.

---

# 2. Trạng thái hiện tại

## Milestone đã đạt

```text
Recommendation Profile Intelligence MVP
+
Phase 5.5 Longitudinal Profile Evolution — CORE IMPLEMENTED
```

Pipeline hiện tại:

```text
Browser profile
   ↓
Home
   +
Subscriptions read-only
   +
random Home seeds → Up Next replay
   ↓
YouTube API enrichment
   ↓
classifier
   ↓
session profile
   ↓
DAILY OBSERVATION
   ↓
temporal decay / rolling windows
   ↓
LONGITUDINAL CURRENT PROFILE
   ↓
creator opportunity + creative blueprint
```

Phase 5.5 đã implement code. Việc còn lại của Phase 5.5 là **validation bằng dữ liệu thật trong ít nhất 3–7 ngày/profile**, không phải thêm kiến trúc lớn mới.

Sau validation:

# Phase 6 — Initial Viewer / Viewer Robot Generator

---

## 3. Tiến độ roadmap

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Schema / conventions | ~90% |
| 1 | 18 Level-1 Categories | 100% |
| 2 | Niche → Sub-niche → Topic → Subtopic | ~50% |
| 3 | Keyword Index | ~70% |
| 4 | Relationship Graph | ~30% |
| 5 | Video Content Classification | ~90% / MVP usable |
| **5.5** | **Longitudinal Profile Evolution** | **Core implemented — validation pending** |
| 6 | Initial Viewer Generator | 0% — NEXT after validation |
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

# 4. Các lớp evidence hiện tại

Không trộn tất cả evidence thành một loại.

```text
RECOMMENDATION EXPOSURE
├── Home
└── Up Next

EXPLICIT AFFINITY
└── Subscriptions

HISTORICAL STATE
└── Daily observations

OBSERVED BEHAVIOR
└── chưa dùng trong profile thật hiện tại
```

### Home

Profile-level recommendation prior.

### Up Next

Contextual recommendation neighborhood của seed video.

Replay dùng để đo stability/volatility và được normalize theo seed/replay để số request lớn không tự động áp đảo Home.

### Subscriptions

Extension 0.5.0 đọc read-only:

```text
/feed/subscriptions
/feed/channels
```

Thu được:

- video từ subscriptions feed để enrich/classify;
- channel quan sát được từ subscribed-channel page.

Subscriptions là explicit-affinity evidence, **không phải watch history**.

Không suy luận unsubscribe chỉ vì channel biến mất khỏi một snapshot vì page payload có thể không đầy đủ/paginated.

---

# 5. Phase 5.5 — implementation hiện tại

## 5.1 Daily observation

Default research cadence:

```text
1 profile
→ khoảng 1 collection / ngày
```

Extension hiện vẫn được người dùng bấm collect; **chưa có unattended automatic scheduler**.

Nếu collect nhiều lần cùng calendar day:

```text
latest collection
→ thay daily observation của ngày đó
```

Raw session/surface evidence vẫn lưu để debug, nhưng longitudinal engine chỉ tính một daily observation cho ngày đó.

Daily files:

```text
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
```

## 5.2 Surface priors

Khi đủ cả ba category distributions:

```text
Home           0.53
Up Next        0.32
Subscriptions  0.15
```

Nếu thiếu surface, các prior còn lại được renormalize.

Đây là heuristic của dự án, không phải trọng số YouTube.

## 5.3 Temporal windows

Profile hiện có:

```text
Today
7d
30d
Long-term
```

Decay:

```text
weight(age) = 0.5 ** (age_days / half_life_days)
```

Initial parameters:

```text
7d         half-life 3.5 ngày
30d        half-life 14 ngày
long-term  half-life 60 ngày
```

Current profile mix:

```text
0.50 × Today
+ 0.30 × 7d
+ 0.15 × 30d
+ 0.05 × Long-term
```

Mục tiêu: một ngày bất thường không được thay hoàn toàn hồ sơ đã hình thành.

## 5.4 Trend states

Interest có thể mang:

```text
baseline
emerging
rising
stable
cooling
dormant
revived
```

Ngày đầu tiên dùng `baseline` vì chưa đủ history để giả định rising/cooling.

Trend là nhãn của dự án từ daily observations, không phải nhãn của YouTube.

## 5.5 Stable profile naming

Profile name không đổi vì một snapshot.

Có:

```text
stable_name
candidate_name
candidate_consecutive_days
previous_names
```

Existing stable name chỉ được thay nếu candidate mới tồn tại đủ 3 daily observations liên tiếp.

Tên profile vẫn là nhãn nghiên cứu, không phải YouTube internal label.

## 5.6 Keyword / tag trends

Keyword và tag có:

```text
Today
7d
30d
Long-term
trend_state
```

Subscriptions metadata được dùng như affinity/semantic evidence phụ, không biến tags thành recommendation-control mechanism.

## 5.7 Observed subscribed-channel affinity

Profile lưu:

```text
channel_id
name
observed_today
observed_days
first_seen
last_seen
```

Absence không đồng nghĩa unsubscribe.

---

# 6. Output hiện tại

Người dùng vẫn chỉ cần nhìn **một current report** cho mỗi browser profile:

```text
data/profile_reports/profile_<id>__current.profile.json
data/profile_reports/profile_<id>__current.profile.html
```

Persistent profile state:

```text
data/profile_library/profile_<id>.json
data/profile_library/profile_<id>.history.jsonl
data/profile_library/daily/profile_<id>/YYYY-MM-DD.json
data/profile_library/index.json
```

Raw evidence:

```text
data/home_*/profile_<id>/
data/up_next_*/profile_<id>/
data/subscriptions_*/profile_<id>/
data/collection_sessions/
```

Tất cả personalized data trên được `.gitignore` mặc định.

---

# 7. Report hiện có

Longitudinal HTML hiện hiển thị:

```text
profile stable name
candidate name nếu đang chờ promote
certainty
daily history count
Home item count
Up Next replay count
Subscriptions video/channel count

interest weights
- current
- Today
- 7d
- 30d
- Long-term
- trend state
- Home support
- Up Next support
- Subscription support

content series plan
creative blueprint
keyword trends
tag trends
observed subscribed channels
stable Up Next
```

Creator strategy tiếp tục dùng:

```text
ANCHOR                 60–70%
BRIDGE                 20–30%
CONTROLLED EXPANSION   <=10–15%
```

Temporal state được dùng để tránh pivot theo một ngày đơn lẻ:

```text
stable / rising → ưu tiên anchor/bridge
emerging/revived → candidate expansion
cooling/dormant → không nên pivot kênh chỉ vì historical weight
```

---

# 8. Creative blueprint hiện tại

Mỗi lane có creative brief:

```text
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
- recommended format
- hook
- opening
- context/problem
- main value
- proof/example
- recap / series bridge
- thumbnail direction
```

Creator vẫn tự quyết:

- ý tưởng cụ thể;
- luận điểm;
- script/lời thoại;
- ví dụ/bằng chứng;
- footage/hình ảnh/âm thanh;
- nhịp dựng;
- storytelling;
- claim;
- CTA.

Không viết hộ video hoàn chỉnh.

---

# 9. Version/module checkpoint

### Extension

```text
browser_extension/youtube_home_collector/
  manifest.json       version 0.5.0
  popup.html
  popup.js
  subscriptions.js
```

0.5.0 gồm:

- Home;
- video-only Up Next replay;
- Subscriptions feed read-only;
- subscribed channels read-only;
- last daily collection timestamp trong local extension storage.

### Bridge

```text
scripts/homepage/home_bridge.py
```

Bridge version:

```text
0.8
```

Pipeline finalize:

```text
session profile
→ temporal profile
→ current JSON/HTML
→ profile library
→ daily history
```

### Temporal engine

```text
scripts/profile/build_temporal_profile.py
```

Current longitudinal analysis version:

```text
2.5.0
```

### Session profile / creator brief

```text
scripts/profile/build_consolidated_profile.py
```

Current session analysis version:

```text
2.1.0
```

### Docs/tests

```text
docs/PROFILE_INTELLIGENCE_MODEL.md
docs/LONGITUDINAL_PROFILE_MODEL.md
tests/test_temporal_profile.py
.github/workflows/python-tests.yml
```

---

# 10. Recent implementation commits

```text
7df991b  extension 0.4.1 — Up Next video-only fix
93f3ba8  consolidated profile 2.1 creative blueprint
2dd7bc4  Phase 5.5 temporal engine
fd0d2ee  bridge 0.8 Home + Up Next + Subscriptions + temporal finalize
4ebc8b2  read-only Subscriptions parser
cdc723c  Subscriptions popup controls
0a87aad  daily Subscriptions flow in popup
674ff0c  extension 0.5.0
6e364ed  ignore Subscriptions/temporal personalized data
23b2a3c  longitudinal model documentation
7b9c939  temporal unit tests
69103c4  Python compile/unit-test CI workflow
```

Luôn fetch file hiện tại trước khi sửa; không overwrite bằng SHA cũ từ hội thoại.

---

# 11. Validation cần làm trước Phase 6

Không thêm feature lớn vào Phase 5.5 ngay. Chạy dữ liệu thật trước.

## Minimum validation

Với ít nhất 2–3 browser profiles:

```text
Day 1
Day 2
Day 3
...
Day 7
```

Mỗi ngày collect một lần nếu thuận tiện.

Kiểm tra:

1. extension 0.5.0 vẫn lấy Home đúng;
2. Up Next chỉ còn video đơn, không Mix/playlist;
3. Subscriptions feed trả video đúng;
4. observed subscribed channels hợp lý;
5. cùng ngày collect lại không tăng `daily_observation_count`;
6. sang ngày mới count tăng 1;
7. ngày đầu trend = baseline;
8. sau vài ngày có rising/stable/cooling hợp lý;
9. current weight không nhảy hoàn toàn theo một snapshot;
10. stable profile name không đổi ngay từ một ngày lệch;
11. keyword/tag trends không bị stale/noisy tags áp đảo;
12. HTML current vẫn là một report dễ đọc.

Nếu trend quá nhạy/chậm, tune:

```text
surface priors
half-life
current-window weights
trend thresholds
```

Không gọi tuning này là “tìm đúng thuật toán YouTube”.

---

# 12. Những phần vẫn chưa làm

### Automatic daily scheduler

Chưa làm unattended scheduler.

Hiện daily semantics hoạt động khi người dùng chạy collection. Có thể thêm Chrome alarms/local scheduler về sau nếu thực sự cần, nhưng không nên làm trước khi validation collector ổn.

### Profile maturity

Chưa có nhãn riêng đầy đủ:

```text
new
forming
stable
drifting
```

Có thể suy từ số daily observations + trend volatility sau khi đã có vài ngày dữ liệu.

### Full evidence provenance UI

Raw evidence và session paths đã được lưu, nhưng HTML chưa có click-through provenance chi tiết cho từng weight/keyword.

### Channel affinity ngoài Subscriptions

Chưa aggregate đầy đủ:

```text
channel repeated on Home
+
channel repeated in Up Next
+
subscribed channel
```

### Freshness / duration / language preference

Đã có một phần metadata foundation nhưng chưa thành longitudinal profile dimensions riêng.

### Baseline/control profile

Chưa làm:

```text
profile exposure
-
common/control exposure
→ profile-specific signal proxy
```

Đây là ưu tiên cao sau khi daily data ổn.

### Transition persistence

Chưa có learned multi-day graph:

```text
Topic A → Topic B
```

qua nhiều ngày/seed.

### Classifier v3

Còn các việc:

- topicDetails → internal taxonomy normalization;
- broad official category reliability;
- contextual AI;
- intent fixes;
- stale tag handling mạnh hơn;
- entity expansion;
- labeled evaluation set.

### API metadata cache

Chưa cache theo `video_id`; cần làm để giảm quota khi replay/session lặp video.

### Channel DNA / candidate scoring module

Chưa có module riêng để nhập idea creator và chấm:

```text
Profile fit
Channel DNA fit
Home overlap
Up Next overlap
Subscription affinity
Keyword overlap
Demand
Freshness
Series continuity
Temporal trend
```

---

# 13. Next step chính thức

## Trước tiên

**Validate Phase 5.5 trong 3–7 ngày.**

Không cần chờ đủ 7 ngày để sửa bug collector nếu phát hiện lỗi rõ ràng.

## Sau khi temporal state ổn

# Phase 6 — Initial Viewer / Viewer Robot Generator

Hai seed mode:

```text
pure synthetic
observed-profile-prior seeded
```

Observed-profile-prior lúc này dùng longitudinal `profile_library/profile_<id>.json`, không dùng một Home snapshot đơn lẻ.

Viewer Robot từ Phase 6 trở đi vẫn chạy synthetic/offline.

---

# 14. Sau Phase 6

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

# 15. Câu mở đầu cho cuộc trò chuyện sau

Để validate Phase 5.5:

> Đọc `PLAN.md`. Tôi đã collect dữ liệu mới bằng extension 0.5.0. Kiểm tra longitudinal profile, Subscriptions và trend states trước khi sang Phase 6.

Khi đã validation ổn:

> Đọc `PLAN.md` và bắt đầu Phase 6 — Initial Viewer / Viewer Robot Generator, dùng longitudinal profile hiện tại làm một optional observed-profile prior.

---

# 16. Safety / scope bắt buộc

- Collector thật chỉ read-only.
- Không tự click/play/like/comment/subscribe/unsubscribe.
- Không fake traffic/view/engagement.
- Recommendation exposure không phải watch behavior thật.
- Subscriptions là explicit affinity, không phải recommendation surface hay watch history.
- Viewer Robot từ Phase 6 phải synthetic/offline.
- Creator opportunity score là heuristic nghiên cứu, không đảm bảo impressions/views.
- Official YouTube metadata là evidence/reference, không phải semantic ground truth.
- Không gọi coverage/separability là accuracy nếu chưa có labeled ground truth.
