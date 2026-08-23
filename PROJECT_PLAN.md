# YouTube Library — Project Plan

## 1. Mục tiêu dự án

`youtube_library` là kho dữ liệu nền cho một hệ thống mô phỏng hệ sinh thái nội dung YouTube theo hai phía:

1. **Viewer Robot** — robot người xem được sinh ra với một thiên hướng sở thích ban đầu, sau đó tương tác với feed mô phỏng để dần hình thành hồ sơ hành vi riêng.
2. **Creator Model** — phía nhà sáng tạo quan sát các nhóm hồ sơ người xem, lựa chọn chủ đề/nội dung phù hợp với một nhóm audience và kiểm tra khả năng nội dung đó được nhóm người xem tương ứng quan tâm trong môi trường mô phỏng.

Taxonomy nội dung là ngôn ngữ chung của toàn bộ hệ thống.

Luồng tổng quát:

```text
CONTENT DICTIONARY
      │
      ├──────────────► VIEWER ROBOTS
      │                    │
      │                    ▼
      │               INTERACTIONS
      │                    │
      │                    ▼
      │              USER PROFILES
      │                    │
      │                    ▼
      │             AUDIENCE CLUSTERS
      │                    │
      │                    ▼
      └──────────────► CREATOR STRATEGY
                           │
                           ▼
                      CREATOR VIDEO
                           │
                           ▼
                   VIEWER ↔ VIDEO MATCH
                           │
                           ▼
                     NEXT INTERACTION
                           │
                           └──────────► vòng lặp tiếp theo
```

> Phạm vi của dự án là **mô phỏng/nghiên cứu offline**. Không sử dụng robot để tạo lượt xem, click, like, comment hoặc tương tác giả trên YouTube thật.

---

# 2. Các khái niệm cốt lõi

## 2.1 Content Taxonomy

Mỗi video được mô tả bằng cây nội dung:

```text
Category
  └── Niche
      └── Sub-niche
          └── Topic
              └── Subtopic
                  └── Keywords
```

Ví dụ:

```text
Science & Technology
└── Artificial Intelligence
    └── AI Agents
        └── Tool-using Agents
            └── MCP
```

Một video **không bắt buộc chỉ thuộc một Category**. Nó có thể có nhiều nhãn với trọng số khác nhau.

Ví dụ:

```json
{
  "science_technology": 0.45,
  "business_finance": 0.35,
  "education": 0.20
}
```

## 2.2 Viewer Profile

Viewer không bị gắn cứng vào một thể loại duy nhất. Mỗi robot có một phân bố sở thích:

```json
{
  "entertainment": 0.55,
  "gaming": 0.25,
  "music": 0.12,
  "technology": 0.08
}
```

Phân bố này thay đổi theo lịch sử tương tác.

## 2.3 Related Interests

Một người thích thể loại `I` có thể có xác suất quan tâm thêm `B`, `C`, `F`.

Ví dụ:

```text
Entertainment
├── Comedy      0.62
├── Music       0.48
├── Lifestyle   0.41
└── Gaming      0.17
```

Có hai loại quan hệ:

- `semantic`: hai nội dung gần nhau về ý nghĩa.
- `behavioral`: trong dữ liệu mô phỏng, người xem một nhóm thường chuyển sang nhóm khác.

## 2.4 Creator Target

Creator có thể chọn một nhóm audience rồi xây nội dung tương ứng:

```text
Audience Cluster
    ↓
Category
    ↓
Niche
    ↓
Topic
    ↓
Keywords
    ↓
Creator Video Profile
```

Video của creator sau đó được đưa vào feed mô phỏng khi mức phù hợp với một viewer đủ cao.

---

# 3. Content Dictionary cấp 1

Bộ Category khởi đầu:

1. Entertainment — Giải trí
2. News & Politics — Tin tức & Chính trị
3. Music — Âm nhạc
4. Gaming — Trò chơi
5. Sports — Thể thao
6. Film & Animation — Phim & Hoạt hình
7. Education — Giáo dục
8. Science & Technology — Khoa học & Công nghệ
9. People & Lifestyle — Con người & Cuộc sống
10. How-to & Style — Hướng dẫn & Phong cách
11. Travel & Events — Du lịch & Sự kiện
12. Autos & Vehicles — Xe & Phương tiện
13. Pets & Animals — Thú cưng & Động vật
14. Comedy — Hài
15. Society & Community — Xã hội & Cộng đồng
16. Business & Finance — Kinh doanh & Tài chính
17. Health & Fitness — Sức khỏe & Thể chất
18. Food & Cooking — Ẩm thực

Danh sách này là taxonomy nội bộ của dự án. Các Category chính thức của YouTube sẽ được lưu riêng để làm lớp tham chiếu/mapping.

---

# 4. Roadmap triển khai

## Phase 0 — Chuẩn hóa mô hình dữ liệu

### Mục tiêu

Tạo quy ước chung để mọi Category, Topic, keyword, relation, viewer và video sử dụng cùng một schema.

### Cách thực hiện

1. Quy định ID dạng machine-readable:

```text
technology
technology.ai
technology.ai.agents
technology.ai.agents.mcp
```

2. Mỗi node taxonomy tối thiểu có:

```json
{
  "id": "technology.ai.agents",
  "type": "topic",
  "name": {
    "en": "AI Agents",
    "vi": "AI Agent"
  },
  "parent": "technology.ai"
}
```

3. Quy định version cho taxonomy:

```text
0.1.0
0.2.0
1.0.0
```

4. Không đổi ID chỉ vì đổi tên hiển thị.

### Đầu ra

- `schemas/`
- naming conventions
- ID conventions
- taxonomy versioning rules

### Hoàn thành khi

Mọi entity đều có thể được xác định bằng ID ổn định và validate được bằng schema.

---

## Phase 1 — Xây Content Categories

### Mục tiêu

Tạo Level 1 của từ điển nội dung.

### Cách thực hiện

Với từng Category cần lưu:

- ID
- tên tiếng Anh
- tên tiếng Việt
- mô tả
- phạm vi nội dung
- nội dung nên thuộc Category này
- nội dung dễ nhầm với Category khác
- Category liên quan
- mapping với YouTube category nếu có

Ví dụ:

```json
{
  "id": "gaming",
  "name": {
    "en": "Gaming",
    "vi": "Trò chơi"
  },
  "description": "Nội dung tập trung vào trò chơi điện tử, gameplay, esports và văn hóa gaming.",
  "related": [
    "entertainment",
    "technology",
    "sports"
  ]
}
```

### Đầu ra

```text
taxonomy/categories/
```

### Hoàn thành khi

Một người có thể đọc định nghĩa và phân biệt rõ tất cả Category cấp 1.

---

## Phase 2 — Phân rã Niche, Sub-niche, Topic

### Mục tiêu

Biến Category rộng thành cây nội dung đủ chi tiết để classify video và tạo sở thích robot.

### Cách thực hiện

Với mỗi Category:

```text
Category
→ 5–20 Niches
→ mỗi Niche có Sub-niches
→ mỗi Sub-niche có Topics
→ Topics quan trọng có Subtopics
```

Ví dụ:

```text
Science & Technology
├── Artificial Intelligence
│   ├── Generative AI
│   ├── AI Agents
│   ├── AI Coding
│   ├── Machine Learning
│   └── Robotics
├── Programming
├── Cybersecurity
├── Consumer Technology
└── Science
```

Không ép cây phải cân bằng. Một nhánh phổ biến có thể sâu hơn nhánh khác.

### Quy tắc

Một node mới chỉ nên được tạo nếu nó có ích cho ít nhất một trong các mục tiêu:

- classify video tốt hơn;
- mô tả sở thích viewer tốt hơn;
- phân biệt audience tốt hơn;
- creator có thể thực sự nhắm nội dung vào node đó.

### Đầu ra

```text
taxonomy/niches/
taxonomy/topics/
taxonomy/subtopics/
```

### Hoàn thành khi

Một video phổ biến bất kỳ có thể tìm được ít nhất một đường dẫn hợp lý trong taxonomy.

---

## Phase 3 — Xây Keyword Index

### Mục tiêu

Tạo bộ từ khóa để ánh xạ title/description/transcript của video vào taxonomy.

### Cách thực hiện

Mỗi node có các nhóm keyword:

```json
{
  "primary": [],
  "secondary": [],
  "aliases": [],
  "vi": [],
  "en": [],
  "abbreviations": [],
  "entities": [],
  "negative": []
}
```

Ví dụ:

```json
{
  "topic": "technology.ai.agents",
  "primary": [
    "ai agent",
    "ai agents",
    "agentic ai"
  ],
  "secondary": [
    "tool calling",
    "multi-agent",
    "agent memory"
  ],
  "aliases": [
    "autonomous agent"
  ],
  "vi": [
    "tác nhân ai",
    "ai tự động"
  ]
}
```

### Nguyên tắc

Không classify chỉ vì xuất hiện một keyword chung chung.

Ví dụ `Apple` có thể là:

- công ty công nghệ;
- trái táo;
- một tên riêng khác.

Do đó cần kết hợp nhiều tín hiệu.

### Đầu ra

```text
keywords/categories/
keywords/niches/
keywords/topics/
```

### Hoàn thành khi

Mỗi Category và các Topic quan trọng đều có keyword seed đủ để bắt đầu classifier rule-based.

---

## Phase 4 — Xây Content Relationship Graph

### Mục tiêu

Mô tả các đường chuyển sở thích khả dĩ giữa Category/Topic.

### Cách thực hiện

Mỗi cạnh gồm:

```json
{
  "source": "technology.ai",
  "target": "education.programming",
  "type": "adjacent_interest",
  "weight": 0.55,
  "source_type": "seed"
}
```

Các relation type ban đầu:

```text
parent_of
child_of
related_to
adjacent_interest
semantic_overlap
```

Sau khi có simulation sẽ bổ sung:

```text
co_interest
next_watch
co_watch
```

### Seed graph

Ví dụ:

```text
Technology ↔ Education
Technology ↔ Business
Gaming ↔ Entertainment
Gaming ↔ Technology
Sports ↔ Health
Food ↔ Health
Travel ↔ Food
Finance ↔ News
Entertainment ↔ Comedy
Entertainment ↔ Music
```

### Lưu ý

Seed weight không phải sự thật thống kê. Nó chỉ là prior để mô phỏng ban đầu.

### Đầu ra

```text
relations/semantic/
relations/adjacent-interest/
```

### Hoàn thành khi

Mọi Category có ít nhất một số đường chuyển hợp lý sang các Category lân cận.

---

## Phase 5 — Video Content Classification

### Mục tiêu

Biến một video thành `Content Vector`.

### Input

Có thể sử dụng:

- title
- description
- tags
- transcript
- channel context
- playlist context

### Cách thực hiện

#### Bước 1 — Keyword match

Đếm và chấm trọng số keyword xuất hiện.

#### Bước 2 — Context match

Xem các keyword có xuất hiện cùng nhau hay không.

#### Bước 3 — Candidate topics

Tạo danh sách topic ứng viên.

#### Bước 4 — Normalize score

Ví dụ:

```json
{
  "categories": {
    "science_technology": 0.45,
    "business_finance": 0.35,
    "education": 0.20
  },
  "topics": {
    "technology.ai": 0.91,
    "business.investing": 0.64
  }
}
```

#### Bước 5 — Confidence

Lưu confidence riêng với score.

### Đầu ra

```text
content/profiles/<video_id>.json
```

### Hoàn thành khi

Một tập video kiểm thử có thể được classify hợp lý bằng nhiều nhãn có trọng số.

---

## Phase 6 — Initial Viewer Generator

### Mục tiêu

Sinh robot người xem khi chưa có lịch sử.

### Cách thực hiện

Mỗi robot được tạo từ các tham số:

```json
{
  "primary_interests": [],
  "secondary_interests": [],
  "low_interests": [],
  "exploration_rate": 0.1,
  "novelty_tolerance": 0.2
}
```

### Random nhưng có cấu trúc

Không random mọi Category độc lập và đều nhau.

Quy trình:

1. random một `primary category`;
2. chọn 1–3 secondary categories từ relationship graph;
3. chọn niche/topic bên trong primary category;
4. thêm một tỷ lệ nhỏ unrelated exploration;
5. normalize thành vector.

Ví dụ:

```text
Robot A

Entertainment   0.45
Gaming          0.25
Music           0.15
Lifestyle       0.10
News            0.05
```

### Đầu ra

```text
viewers/profiles/initial/
```

### Hoàn thành khi

Sinh được số lượng lớn robot nhưng vẫn có profile đa dạng và hợp lý.

---

## Phase 7 — Feed Simulation

### Mục tiêu

Tạo môi trường feed để robot bắt đầu tương tác.

### Cách thực hiện

Feed mỗi vòng chứa hỗn hợp:

```text
known interests
adjacent interests
exploration content
```

Ví dụ seed ban đầu:

```text
70% nội dung gần sở thích
20% nội dung lân cận
10% exploration
```

Các tỷ lệ chỉ là tham số thử nghiệm, không coi là hành vi thật của YouTube.

Mỗi item feed gồm:

```json
{
  "video_id": "...",
  "content_vector": {},
  "position": 1,
  "source": "simulation"
}
```

### Đầu ra

Một batch feed cho mỗi viewer/session.

### Hoàn thành khi

Feed có đủ diversity và không khóa robot vào một Category duy nhất.

---

## Phase 8 — Interaction Simulation

### Mục tiêu

Cho robot quyết định skip/click/watch dựa trên profile thay vì hard-code.

### Hành vi hỗ trợ

```text
impression
skip
click
watch
partial_watch
complete
rewatch
like
save
```

### Cách thực hiện

Tính utility:

```text
interest similarity
+ adjacent-interest bonus
+ novelty preference
+ exploration noise
+ format preference
= interaction probability
```

Sau đó sampling hành động từ probability.

### Quy tắc quan trọng

Không được viết:

```text
if video.category == viewer.primary:
    click = true
```

Phải có xác suất để cùng một viewer đôi khi skip đúng sở thích và đôi khi thử nội dung mới.

### Đầu ra

```text
simulation/interactions/*.jsonl
```

### Hoàn thành khi

Hai robot cùng Category chính vẫn có lịch sử tương tác khác nhau.

---

## Phase 9 — Interest Learning

### Mục tiêu

Để profile robot phát triển từ interaction history.

### Cách thực hiện

Mỗi interaction tạo một tín hiệu update.

Ví dụ seed weights:

```text
click             +0.5
watch 25%         +1
watch 50%         +2
watch 80%         +4
watch 95%         +5
like              +2
save              +4
rewatch           +5
early exit        -1
not interested    -6
```

Các giá trị trên chỉ là tham số mô phỏng ban đầu.

Update không chỉ Category mà cả Topic.

Ví dụ video:

```text
Technology       0.6
Education        0.4
AI Agents        0.9
Programming      0.5
```

Nếu interaction mạnh, toàn bộ vector được đóng góp vào viewer profile theo trọng số.

### Ba loại interest

Lưu riêng:

```text
seed_interest
observed_interest
inferred_interest
```

Không cho inferred interest tự khuếch đại vô hạn.

### Đầu ra

```text
viewers/profiles/learned/
```

### Hoàn thành khi

Profile sau nhiều interaction phản ánh history nhưng vẫn giữ được exploration.

---

## Phase 10 — Behavior Profile / Archetypes

### Mục tiêu

Phân biệt `viewer thích gì` và `viewer xem theo kiểu nào`.

### Archetype seed

```text
Explorer
Specialist
Learner
Researcher
Fan / Loyalist
Trend Follower
News Seeker
Entertainment Seeker
Problem Solver
Casual Viewer
Binge Viewer
Variety Viewer
```

### Cách thực hiện

Tính feature từ interaction history:

```text
category diversity
topic diversity
completion rate
repeat rate
channel concentration
exploration rate
session depth
recency sensitivity
```

Ví dụ:

- diversity cao + nhiều topic mới → `Explorer`;
- concentration cao + repeat cao → `Specialist/Loyalist`;
- completion cao ở tutorial/deep-dive → `Learner`;
- nhiều comparison/review trước khi chuyển topic → `Researcher`.

### Đầu ra

```json
{
  "explorer": 0.72,
  "trend_follower": 0.44,
  "learner": 0.31
}
```

### Hoàn thành khi

Behavior profile được suy từ feature, không gán thủ công theo Category.

---

## Phase 11 — Audience Clustering

### Mục tiêu

Gom nhiều viewer robot thành các phân khúc audience để creator có thể đọc và sử dụng.

### Feature dùng để cluster

- category vector
- topic vector
- behavior vector
- format preferences
- exploration tendency

### Cách thực hiện

Bước đầu có thể dùng rule-based segmentation.

Ví dụ:

```text
Cluster: AI Learners
Primary: Technology / AI
Secondary: Education / Programming
Behavior: Learner + Researcher
```

Khi dữ liệu lớn hơn mới chuyển sang clustering thuật toán.

### Đầu ra

```text
audiences/clusters/
```

Mỗi cluster có:

```json
{
  "id": "ai-learners",
  "size": 0,
  "dominant_interests": {},
  "secondary_interests": {},
  "behaviors": {},
  "topic_transitions": {}
}
```

### Hoàn thành khi

Creator có thể nhìn cluster và hiểu rõ nhóm đó đang xem gì và thường chuyển sang đâu.

---

## Phase 12 — Creator Strategy Model

### Mục tiêu

Cho phía creator chọn một nhóm audience và định nghĩa video muốn nhắm tới.

### Cách thực hiện

Creator chọn:

```text
audience cluster
→ category
→ niche
→ topic
→ adjacent topics
→ keywords
```

Ví dụ:

```text
Audience:
AI Learners

Content:
Technology
→ AI
→ AI Agents
→ MCP
```

Video creator được biểu diễn cùng schema `Content Vector` như mọi video khác.

### Creator Strategy Output

Có thể trả lời:

- audience chính của video;
- audience phụ;
- topic overlap;
- adjacent topics;
- content gaps trong simulation;
- mức match dự kiến với từng cluster.

### Đầu ra

```text
creators/strategies/
creators/content-profiles/
```

### Hoàn thành khi

Creator video có thể được so trực tiếp với viewer profile bằng cùng một taxonomy.

---

## Phase 13 — Viewer ↔ Creator Matching

### Mục tiêu

Mô phỏng khả năng video creator phù hợp với viewer.

### Cách thực hiện

Tạo match score từ:

```text
category similarity
topic similarity
adjacent-interest relations
behavior compatibility
novelty/exploration
```

Ví dụ khái niệm:

```text
match_score =
  interest_similarity
  + topic_overlap
  + related_interest_bonus
  + exploration_component
```

Không đặt creator video tự động được click.

Match score chỉ quyết định khả năng video được đưa vào **feed mô phỏng** hoặc vị trí tương đối trong candidate set.

Viewer vẫn thực hiện interaction simulation bình thường.

### Đầu ra

```text
simulation/matches/
```

### Hoàn thành khi

Một creator video phù hợp cao có xác suất được chọn cao hơn nhưng không phải 100%.

---

## Phase 14 — Closed-loop Simulation

### Mục tiêu

Kết nối tất cả thành vòng lặp hoàn chỉnh.

### Luồng

```text
Viewer Profile
     ↓
Feed Generation
     ↓
Creator Content Candidate
     ↓
Matching
     ↓
Viewer Interaction
     ↓
Profile Update
     ↓
Audience Cluster Update
     ↓
Creator Strategy Update
     ↓
New Content
     ↓
Feed Generation
```

### Cách thực hiện

Simulation chạy theo `step` hoặc `session`.

Mỗi vòng lưu snapshot để có thể replay/debug.

Ví dụ:

```text
run_id
viewer_id
step
feed
interaction
profile_before
profile_after
```

### Đầu ra

Một simulation có thể tái lập bằng seed ngẫu nhiên.

### Hoàn thành khi

Cùng một seed cho ra cùng kết quả; đổi seed tạo được hệ sinh thái khác.

---

## Phase 15 — Learned Transition Graph

### Mục tiêu

Học từ simulation thay vì chỉ dựa vào relationship seed.

### Cách thực hiện

Đếm chuyển tiếp:

```text
A → B
A → C
B → D
```

Ước lượng:

```text
P(next_topic = B | current_topic = A)
```

Ví dụ:

```text
AI → Programming     0.68
AI → Education       0.54
AI → Business        0.39
```

Lưu tách:

```text
seed_relationship
learned_relationship
```

Không ghi đè seed graph bằng learned graph.

### Đầu ra

```text
relations/transitions/
relations/co-interest/
```

### Hoàn thành khi

Có thể giải thích đường chuyển sở thích bằng số liệu simulation.

---

## Phase 16 — Evaluation

### Mục tiêu

Đảm bảo robot không hành xử quá máy móc và model không tự khuếch đại bias.

### Metrics

```text
category diversity
topic diversity
exploration rate
repeat rate
profile stability
interest drift
cross-category transition
creator-match acceptance
cluster stability
```

### Kiểm thử cần có

#### Test 1 — Không khóa Category

Robot Gaming vẫn phải có xác suất khám phá Technology/Entertainment.

#### Test 2 — Không random hoàn toàn

Robot đã có profile mạnh phải ưu tiên nội dung liên quan hơn noise.

#### Test 3 — Negative signal

Một chuỗi skip/early-exit phải giảm affinity.

#### Test 4 — Interest drift

Nếu robot liên tục xem topic mới, profile phải thay đổi theo thời gian.

#### Test 5 — Creator targeting

Video match đúng cluster phải có kết quả tốt hơn video unrelated trong simulation.

### Hoàn thành khi

Simulation tạo được hành vi đa dạng nhưng vẫn có cấu trúc và giải thích được.

---

# 5. Cấu trúc repo đề xuất

```text
youtube_library/
│
├── PROJECT_PLAN.md
│
├── taxonomy/
│   ├── categories/
│   ├── niches/
│   ├── topics/
│   └── subtopics/
│
├── keywords/
│   ├── categories/
│   ├── niches/
│   └── topics/
│
├── relations/
│   ├── semantic/
│   ├── adjacent-interest/
│   ├── co-interest/
│   └── transitions/
│
├── content/
│   ├── classifier/
│   └── profiles/
│
├── viewers/
│   ├── generator/
│   ├── archetypes/
│   └── profiles/
│
├── audiences/
│   └── clusters/
│
├── creators/
│   ├── strategies/
│   └── content-profiles/
│
├── simulation/
│   ├── feed/
│   ├── interactions/
│   ├── matching/
│   └── runs/
│
├── schemas/
│
├── examples/
│
└── docs/
```

---

# 6. Thứ tự thực hiện thực tế

Không triển khai toàn bộ cùng lúc.

## Milestone 0.1 — Content Dictionary

Làm trước:

1. Category schema.
2. 18 Category cấp 1.
3. Niche của từng Category.
4. Topic chính.
5. Keyword tiếng Việt + tiếng Anh.
6. Related-interest seed graph.

### Definition of Done

Một video bất kỳ có thể được biểu diễn thành:

```text
Category Vector
+
Topic Vector
+
Keyword Evidence
```

---

## Milestone 0.2 — Viewer Simulation

Sau khi taxonomy ổn định:

1. Viewer schema.
2. Random profile generator.
3. Feed generator.
4. Interaction model.
5. Interest update model.
6. Behavior archetypes.

### Definition of Done

Có thể sinh Robot A và chạy nhiều session để nó tự hình thành hồ sơ riêng.

---

## Milestone 0.3 — Audience Model

1. Gom viewer profiles.
2. Tạo audience clusters.
3. Tính primary/secondary interests.
4. Tính topic transitions.

### Definition of Done

Có thể trả lời:

```text
Nhóm audience này thường xem gì?
Có thể xem thêm gì?
Có đặc trưng hành vi nào?
```

---

## Milestone 0.4 — Creator Simulation

1. Creator target schema.
2. Content strategy profile.
3. Viewer-video matching.
4. Candidate insertion vào feed mô phỏng.
5. Đo interaction result.

### Definition of Done

Creator có thể chọn một audience cluster, tạo một content vector và mô phỏng khả năng nhóm viewer đó quan tâm.

---

## Milestone 1.0 — Closed-loop Ecosystem

Kết nối:

```text
Taxonomy
→ Viewer
→ Interaction
→ Profile
→ Audience
→ Creator
→ Content
→ Matching
→ Interaction
→ Profile update
```

### Definition of Done

Có thể chạy một simulation nhiều vòng, lưu toàn bộ state và tái lập kết quả bằng random seed.

---

# 7. Nguyên tắc thiết kế bắt buộc

## 7.1 Taxonomy là nền tảng chung

Viewer, video và creator đều phải dùng cùng ID taxonomy.

## 7.2 User không thuộc duy nhất một Category

Viewer luôn là vector nhiều sở thích.

## 7.3 Video không thuộc duy nhất một Category

Video luôn có thể mang nhiều nhãn với trọng số.

## 7.4 Seed và learned data phải tách riêng

Không trộn giả định ban đầu với dữ liệu được học từ simulation.

## 7.5 Không để inferred interest tự khuếch đại

Sở thích suy luận phải có decay/giới hạn và không được coi ngang bằng tương tác quan sát trực tiếp.

## 7.6 Random phải reproducible

Mọi simulation cần có `random_seed`.

## 7.7 Mọi quyết định quan trọng phải giải thích được

Ví dụ phải truy được:

```text
Tại sao Robot A thích AI?
→ vì đã xem các video X/Y/Z.

Tại sao video Creator C match Robot A?
→ vì overlap AI Agents + Programming + Education.
```

## 7.8 Giữ simulation tách khỏi YouTube thật

Không thiết kế hệ thống nhằm tạo traffic, lượt xem hoặc tương tác giả trên nền tảng thật.

---

# 8. Bước thực hiện tiếp theo

Công việc tiếp theo của repo là **Milestone 0.1 — Content Dictionary**.

Thứ tự cụ thể:

```text
1. Tạo schema Category
2. Tạo 18 Category
3. Phân rã Category 01: Entertainment
4. Thu gom keywords cho Entertainment
5. Tạo related-interest cho Entertainment
6. Lặp lại với News & Politics
7. Music
8. Gaming
9. Sports
10. ... đến hết 18 Category
11. Review toàn taxonomy
12. Tạo classifier thử nghiệm
```

Sau khi Content Dictionary đủ ổn định mới bắt đầu tạo `Robot A`.

---

# 9. Định nghĩa ngắn gọn của dự án

> **YouTube Library là bộ taxonomy, keyword index và relationship graph dùng để mô phỏng quá trình một viewer robot hình thành sở thích từ các video được tiếp xúc, xây dựng audience behavior profile, sau đó cho phép creator mô phỏng việc lựa chọn nội dung phù hợp với các nhóm audience đó trong một hệ sinh thái recommendation offline.**
