# Video Classification Guide

## 1. Mục tiêu

Tài liệu này mô tả cách xác định một video thuộc Category/Niche/Topic nào trong `CONTENT_DICTIONARY.md`.

Nguyên tắc chính:

> Một video không bị ép vào đúng một Category. Hệ thống tạo một `Content Vector` gồm nhiều Category/Topic với trọng số và confidence.

Ví dụ:

```json
{
  "categories": {
    "science_technology": 0.45,
    "business_finance": 0.35,
    "education": 0.20
  },
  "topics": {
    "science_technology.artificial_intelligence": 0.90,
    "business_finance.investing_stocks": 0.62
  }
}
```

---

# 2. Tín hiệu dùng để phân loại

Ưu tiên theo thứ tự:

1. **Title**
2. **Description**
3. **Tags**
4. **Transcript / captions**
5. **Channel context**
6. **Playlist context**
7. **YouTube category/topic metadata** nếu có
8. **Visual/thumbnail signals** nếu sau này bổ sung model hình ảnh

Không dùng riêng một tín hiệu duy nhất để kết luận khi video mơ hồ.

---

# 3. Tiền xử lý

Trước khi match keyword:

```text
lowercase
unicode normalize
remove duplicate spaces
normalize punctuation
language detect
remove tracking URLs
extract hashtags
extract named entities
```

Ví dụ:

```text
"CHATGPT 5! Cách dùng AI để phân tích CỔ PHIẾU #investing"
```

sau normalize:

```text
chatgpt 5 cách dùng ai để phân tích cổ phiếu investing
```

---

# 4. Keyword Matching

Mỗi topic có các nhóm keyword:

```text
primary
secondary
aliases
entities
negative
```

## 4.1 Trọng số seed

Có thể bắt đầu với:

```text
primary keyword      +5
alias                +4
entity keyword       +4
secondary keyword    +2
negative keyword     -5
```

Các trọng số này chỉ là giá trị khởi đầu để tune.

## 4.2 Exact phrase ưu tiên hơn token đơn

Ví dụ:

```text
"artificial intelligence" > "artificial" + "intelligence"
```

`AI agent` phải mạnh hơn việc chỉ thấy `AI`.

## 4.3 Keyword phải có context

Ví dụ `Apple` không đủ để kết luận Technology.

Nhưng:

```text
Apple + iPhone + iOS + MacBook
```

→ confidence Technology cao.

Trong khi:

```text
apple pie + recipe + baking
```

→ Food & Cooking.

---

# 5. Context Matching

Không chỉ đếm keyword. Cần đo các cụm keyword xuất hiện cùng nhau.

Ví dụ video:

```text
"Dùng ChatGPT để phân tích cổ phiếu"
```

Các tín hiệu:

```text
ChatGPT → Technology / AI
phân tích → Analysis intent
cổ phiếu → Business & Finance / Investing
```

Kết luận tốt hơn là multi-label:

```text
Science & Technology
Business & Finance
Education/How-to nếu nội dung mang tính hướng dẫn
```

---

# 6. Scoring theo nguồn dữ liệu

Không phải vị trí nào của keyword cũng quan trọng như nhau.

Seed weights gợi ý:

```text
title          x 3.0
tags           x 2.5
description    x 1.8
transcript     x 1.0
channel        x 0.6
playlist       x 0.7
```

Ví dụ keyword `AI Agent` xuất hiện trong title phải mạnh hơn xuất hiện một lần ở transcript 30 phút.

---

# 7. Frequency và Density

Transcript dài dễ tạo false positive nếu chỉ đếm số lần.

Cần dùng cả:

```text
frequency = số lần keyword xuất hiện

density = số lần / tổng token
```

Ví dụ 10 lần `football` trong transcript 1.000 từ mạnh hơn 10 lần trong transcript 50.000 từ.

Có thể dùng log-frequency để tránh spam keyword:

```text
keyword_score = log(1 + frequency)
```

---

# 8. Hierarchical Classification

Classifier nên đi từ rộng đến sâu.

```text
Category
  ↓
Niche
  ↓
Topic
  ↓
Subtopic
```

Ví dụ:

```text
Science & Technology
→ Artificial Intelligence
→ AI Agents
→ MCP
```

Không classify trực tiếp `MCP` nếu parent `AI Agents` không có đủ evidence, trừ trường hợp entity đặc biệt rõ ràng.

---

# 9. Parent Propagation

Nếu một Topic được nhận diện mạnh, parent Category cũng phải nhận score.

Ví dụ:

```text
MCP score = 0.91
```

thì propagate:

```text
AI Agents
Artificial Intelligence
Science & Technology
```

Ví dụ seed:

```text
child score        1.00
parent contribution 0.80
level-2 parent      0.60
```

Sau đó normalize.

---

# 10. Negative Keywords / Disambiguation

Mỗi topic có thể có negative context.

Ví dụ `Java`:

```text
Java + Spring + JVM + coding
→ Programming
```

nhưng:

```text
Java + Indonesia + travel
→ Travel
```

Ví dụ `Python`:

```text
Python + code + pip + Django
→ Programming
```

nhưng:

```text
python + snake + reptile
→ Pets & Animals / Wildlife
```

---

# 11. Named Entities

Entity là tín hiệu rất mạnh nhưng vẫn cần context.

Ví dụ:

```text
ChatGPT
Claude
Gemini
DeepSeek
```

thường liên quan AI.

```text
Bitcoin
Ethereum
Binance
```

thường liên quan Business & Finance / Crypto.

```text
Manchester United
Real Madrid
NBA
UFC
```

thường liên quan Sports.

Entity dictionary nên được version riêng vì tên sản phẩm/nhân vật thay đổi thường xuyên.

---

# 12. Channel Context

Channel context chỉ là tín hiệu phụ.

Ví dụ channel chủ yếu làm Gaming không có nghĩa mọi video đều Gaming.

Seed contribution nên thấp:

```text
channel prior = 0.05–0.15
```

Channel context hữu ích khi title/video quá ngắn hoặc mơ hồ.

---

# 13. Playlist Context

Playlist thường có context mạnh hơn channel.

Ví dụ video tên:

```text
"Episode 14"
```

không đủ để classify.

Nhưng playlist:

```text
"Python for Beginners"
```

cung cấp evidence Education + Programming.

---

# 14. YouTube Metadata

Nếu lấy được:

```text
videoCategoryId
topicDetails.topicIds
topicDetails.relevantTopicIds
```

thì dùng như prior, không coi là output cuối cùng.

Ví dụ YouTube category `Science & Technology` không đủ chi tiết để biết video là AI, smartphone hay astronomy.

---

# 15. Content Intent là dimension riêng

Sau khi xác định video nói về gì, classify thêm `intent`:

```text
tutorial
news
review
comparison
analysis
opinion
reaction
storytelling
documentary
entertainment
case_study
experiment
```

Ví dụ title patterns:

```text
"How to..."                → tutorial
"X vs Y"                   → comparison
"Review..."                → review
"Breaking / vừa xảy ra"    → news
"Tôi thử X trong 30 ngày"  → experiment
"Reaction to..."           → reaction
```

Intent không thay Category.

---

# 16. Format là dimension riêng

Ví dụ:

```text
shorts
long_form
podcast
livestream
clip
course
series
```

Một video có thể là:

```text
Category: Business & Finance
Topic: Investing
Intent: Analysis
Format: Long-form
```

---

# 17. Công thức scoring v1

Một công thức rule-based ban đầu:

```text
raw_topic_score =
    title_match * 3.0
  + tags_match * 2.5
  + description_match * 1.8
  + transcript_match * 1.0
  + playlist_prior * 0.7
  + channel_prior * 0.6
  + youtube_metadata_prior
  - negative_context_penalty
```

Sau đó:

```text
raw topic scores
→ parent propagation
→ normalize
→ confidence calculation
```

---

# 18. Normalization

Có thể dùng softmax hoặc simple normalization.

Simple v1:

```text
normalized_score_i = score_i / sum(all_positive_scores)
```

Không cần ép toàn bộ taxonomy sum = 1 nếu muốn giữ multi-label independent probabilities.

Khuyến nghị ban đầu:

- Category vector normalize tổng = 1.
- Topic scores lưu độc lập trong `[0,1]`.

---

# 19. Confidence

`score` và `confidence` là hai thứ khác nhau.

Ví dụ:

```json
{
  "topic": "gaming",
  "score": 0.70,
  "confidence": 0.25
}
```

có thể xảy ra nếu video rất ít metadata.

Confidence phụ thuộc:

```text
number of independent signals
strength of evidence
agreement between title/description/transcript
data completeness
ambiguity
```

Seed bands:

```text
0.80–1.00 high
0.55–0.79 medium
0.30–0.54 low
<0.30 uncertain
```

---

# 20. Multi-label Threshold

Không lấy duy nhất Top-1.

Ví dụ:

```text
Technology   0.52
Education    0.31
Business     0.13
Comedy       0.04
```

Có thể lưu:

```text
primary category = Technology
secondary category = Education
```

Seed threshold:

```text
primary: top score
secondary: score >= 0.20
weak: 0.08–0.19
ignore: < 0.08
```

Các threshold phải tune bằng tập test.

---

# 21. Ví dụ 1 — AI Investing

Video:

```text
"5 cách dùng ChatGPT phân tích cổ phiếu"
```

Evidence:

```text
ChatGPT → AI
cổ phiếu → Investing
5 cách → Tutorial/How-to intent
```

Output:

```json
{
  "categories": {
    "science_technology": 0.46,
    "business_finance": 0.38,
    "education": 0.16
  },
  "topics": {
    "science_technology.artificial_intelligence": 0.93,
    "business_finance.investing_stocks": 0.85
  },
  "intent": {
    "tutorial": 0.88
  }
}
```

---

# 22. Ví dụ 2 — Football Analysis

Video:

```text
"Vì sao Real Madrid thay đổi chiến thuật ở Champions League?"
```

Evidence:

```text
Real Madrid → football entity
Champions League → football competition
chiến thuật → analysis
```

Output:

```text
Sports              high
Sports/Football     very high
Intent/Analysis     high
```

---

# 23. Ví dụ 3 — Celebrity Music Reaction

Video:

```text
"Reaction MV mới của BLACKPINK"
```

Output có thể là:

```text
Entertainment   0.40
Music           0.38
Comedy/Reaction 0.12
Lifestyle       0.10

Topic:
K-pop
Celebrity
Reaction

Intent:
Reaction
```

Đây là ví dụ cho thấy một video có thể là cầu nối giữa nhiều interest cluster.

---

# 24. Ví dụ 4 — Ambiguous "Python"

Video A:

```text
"Python FastAPI tutorial for beginners"
```

→ Technology / Programming + Education.

Video B:

```text
"Feeding a giant python snake"
```

→ Pets & Animals / Wildlife.

Keyword đơn `python` không được phép tự quyết định Category.

---

# 25. Fallback khi không đủ dữ liệu

Nếu confidence thấp:

```json
{
  "status": "uncertain",
  "categories": {},
  "needs_review": true
}
```

Không ép classifier phải luôn đưa ra đáp án.

Có thể dùng các fallback:

1. broader Category thay vì Topic sâu;
2. channel/playlist prior;
3. model semantic embedding/LLM trong phiên bản sau;
4. manual review cho test set.

---

# 26. Evaluation Dataset

Trước khi dùng classifier cho viewer simulation, cần tạo tập kiểm thử manually labeled.

Mỗi Category tối thiểu nên có:

```text
50 clear examples
20 multi-label examples
20 ambiguous examples
10 negative/adversarial examples
```

18 Category → tối thiểu khoảng 1.800 video examples nếu làm đủ bộ benchmark ban đầu.

Có thể bắt đầu nhỏ hơn, nhưng phải đảm bảo đủ case đa nhãn và mơ hồ.

---

# 27. Metrics

Đánh giá classifier bằng:

```text
precision
recall
F1
multi-label precision@k
multi-label recall@k
hierarchical accuracy
confidence calibration
```

Ngoài metric số cần manual error analysis:

```text
false positive keyword
wrong parent
missed secondary category
entity ambiguity
language ambiguity
```

---

# 28. Pipeline triển khai khuyến nghị

## V0 — Rule Based

```text
title/description/tags/transcript
→ keyword index
→ weighted matching
→ context rules
→ parent propagation
→ content vector
```

Mục tiêu: đơn giản, explainable, dễ debug.

## V1 — Semantic Hybrid

Thêm:

```text
text embedding similarity
```

so với description của từng Topic.

Final score:

```text
keyword score
+ semantic similarity
+ metadata prior
```

## V2 — Learned Classifier

Sau khi có đủ labeled examples:

```text
supervised multi-label classifier
```

Rule-based vẫn được giữ để giải thích và fallback.

---

# 29. Output schema đề xuất

```json
{
  "video_id": "VIDEO_ID",
  "taxonomy_version": "0.1.0",
  "classification_version": "0.1.0",
  "categories": [
    {
      "id": "science_technology",
      "score": 0.46,
      "confidence": 0.90,
      "evidence": [
        "title:chatgpt",
        "description:artificial intelligence"
      ]
    }
  ],
  "topics": [],
  "intent": [],
  "format": null,
  "language": "vi",
  "status": "classified"
}
```

Evidence phải được giữ để có thể giải thích tại sao video được classify như vậy.

---

# 30. Definition of Done

Bước nhận diện video được coi là hoàn thành phiên bản đầu khi:

1. đọc được `CONTENT_DICTIONARY.md`/dữ liệu machine-readable tương ứng;
2. nhận title/description/tags/transcript;
3. trả ra multi-label Category vector;
4. trả ra Topic candidates;
5. có confidence;
6. có evidence;
7. xử lý được ambiguity;
8. không buộc video phải chỉ thuộc một Category;
9. có benchmark test set;
10. classifier đủ ổn định để dùng làm đầu vào cho Viewer Robot simulation.
