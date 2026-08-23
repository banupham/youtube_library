# Homepage Classification v1

## Mục tiêu

Bài thử đầu tiên của dự án là trả lời một câu hỏi đơn giản:

> Chỉ nhìn các video đang xuất hiện trên YouTube Home, hệ thống của chúng ta phân biệt được các Category nội dung tốt đến đâu?

Ở bước này không mô phỏng click/view và không xây viewer profile. Chỉ làm **classification**.

---

## 1. Nguồn dữ liệu

Nguồn chính là các card video đang render trên `https://www.youtube.com/`.

Snapshot Home tối thiểu lấy:

```text
position
video_id
title
channel
url
metadata_text
duration_text
```

Không cần mở video.

Dùng:

```text
scripts/homepage/export_homepage.js
```

Script chỉ đọc DOM hiện tại, không click hoặc play video.

### Vì sao dùng snapshot thay vì YouTube Data API để lấy Home?

YouTube Data API có resource để đọc video, search, category, statistics..., nhưng không có resource công khai tương ứng với personalized Home recommendation feed. Vì vậy Home feed phải được coi là một **input snapshot**; sau khi có `video_id`, ta mới có thể enrich video bằng Data API.

---

## 2. Hai mức classifier

### Level A — `home_visible`

Chỉ sử dụng dữ liệu nhìn thấy ngay trên Home:

```text
title      weight 5.0
channel    weight 0.5
```

Đây là baseline quan trọng nhất, vì nó cho biết bản thân card Home có đủ tín hiệu để phân loại hay không.

### Level B — `enriched`

Nếu sau này bổ sung metadata cho `video_id`, classifier hiện tại đã hỗ trợ:

```text
title                 5.0
channel               0.5
description           1.5
tags                   2.5
youtube_category_id   8.0
```

Mục tiêu sau này là so sánh:

```text
home_visible confidence
VS
enriched confidence
```

để biết API metadata cải thiện phân loại bao nhiêu.

---

## 3. Thuật toán baseline

### Bước 1 — Normalize text

- Unicode NFKC
- lowercase
- giữ tiếng Việt có dấu

### Bước 2 — Keyword match

So title/channel với:

```text
taxonomy/homepage_categories.v1.json
```

Keyword được match theo boundary để tránh lỗi kiểu từ khóa `ai` bị match bên trong một từ tiếng Anh khác.

### Bước 3 — Chấm điểm

Mỗi keyword match đóng góp:

```text
source_weight × keyword_specificity
```

Phrase nhiều từ được ưu tiên hơn token cực ngắn.

### Bước 4 — Multi-label

Không ép một video vào duy nhất một Category.

Ví dụ:

```text
Reaction MV mới...

Entertainment   0.70
Music           0.30
```

được coi là kết quả hợp lệ.

### Bước 5 — Confidence

Classifier trả:

```text
high
medium
low
unknown
```

`unknown` là kết quả hợp lệ, không phải lỗi. Nó có nghĩa dữ liệu Home hiện có chưa đủ để kết luận.

---

## 4. Đo "mức độ phân biệt"

Không dùng accuracy khi chưa có nhãn ground truth.

Ở giai đoạn đầu, đo **separability** bằng các metric:

### `top_share`

Tỷ trọng điểm của Category đứng đầu trên tổng điểm positive.

Ví dụ:

```text
Gaming       0.84
Entertainment 0.16
```

`top_share = 0.84`.

### `margin`

```text
top_share - second_share
```

Margin càng lớn thì video càng dễ phân biệt.

Ví dụ:

```text
Gaming        0.80
Entertainment 0.15
Technology    0.05
```

```text
margin = 0.65
```

### `high_medium_rate`

Tỷ lệ card Home được classifier phân biệt ở confidence `high` hoặc `medium`.

### `ambiguous_or_unknown_rate`

Tỷ lệ `low + unknown`.

Đây là metric chính để quyết định liệu title/channel có đủ hay cần enrich API ngay.

---

## 5. Ngưỡng v1

Baseline hiện dùng:

### High

```text
top_share >= 0.70
margin >= 0.35
```

### Medium

```text
top_share >= 0.50
margin >= 0.15
```

### Low

Có evidence nhưng nhiều Category cạnh tranh nhau.

### Unknown

Không có đủ evidence hoặc điểm raw quá thấp.

Các ngưỡng này là seed configuration, chưa phải tham số tối ưu.

---

## 6. Cách chạy thí nghiệm thật

### Bước A — Capture Home

1. Mở YouTube Home.
2. Không click video.
3. Scroll để load khoảng 50–100 card cho lần audit đầu tiên.
4. Chạy `scripts/homepage/export_homepage.js` trong DevTools Console.
5. Lưu JSON thành ví dụ:

```text
data/home_snapshots/home_001.json
```

Nên lưu thêm context ngoài payload nếu cần:

```text
signed_in / signed_out
country
language
robot_id
session_id
```

### Bước B — Classify

Từ root repo:

```bash
python scripts/classification/classify_homepage.py \
  data/home_snapshots/home_001.json \
  --output data/home_classified/home_001.json
```

### Bước C — Đọc summary

Output chứa:

```json
{
  "summary": {
    "video_count": 100,
    "confidence_counts": {},
    "high_medium_rate": 0.0,
    "ambiguous_or_unknown_rate": 0.0,
    "average_margin": 0.0,
    "top_category_distribution": {}
  }
}
```

Không diễn giải các số `0.0` ở ví dụ này như kết quả; chúng chỉ mô tả schema output.

---

## 7. Cách đánh giá kết quả

### Trường hợp 1 — `high_medium_rate` cao

Nếu phần lớn title/channel đã đủ rõ:

```text
Home Snapshot
→ baseline classifier
→ Category
```

Ta có thể dùng classifier nhẹ cho lượt đầu, chỉ enrich API với các video mơ hồ.

### Trường hợp 2 — Unknown cao

Ví dụ title dạng:

```text
"Tôi không ngờ chuyện này xảy ra..."
```

không nói rõ chủ đề.

Khi đó lấy thêm:

```text
description
tags
youtube categoryId
topicDetails
```

### Trường hợp 3 — Low cao

Đây thường là content lai:

```text
Reaction + Music
AI + Finance
Sports + News
Food + Travel
```

Không nhất thiết phải ép thành single-label. Multi-label có thể chính xác hơn với mục tiêu behavioral profile.

---

## 8. Dữ liệu cần inspect thủ công sau mỗi batch

Mỗi batch nên chọn ngẫu nhiên một số video trong 4 nhóm:

```text
high
medium
low
unknown
```

Kiểm tra:

1. top Category có hợp lý không;
2. Category thứ hai có hợp lý không;
3. keyword nào tạo ra score;
4. keyword nào gây false positive;
5. topic/entity nào còn thiếu trong dictionary.

Đây là vòng cập nhật dictionary:

```text
Home snapshot
→ classify
→ inspect errors
→ update dictionary
→ classify lại
```

---

## 9. Sanity-check example

Repo có:

```text
examples/homepage_snapshot.example.json
```

Đây chỉ là dữ liệu minh họa để kiểm tra script chạy đúng, **không phải Home feed thật và không được dùng để báo accuracy**.

Chạy:

```bash
python scripts/classification/classify_homepage.py \
  examples/homepage_snapshot.example.json
```

---

## 10. Definition of Done cho Classification v1

Classification v1 được coi là đủ để sang bước tiếp theo khi:

1. capture được Home snapshot ổn định;
2. classifier chạy được trên ít nhất vài batch Home thực;
3. biết `high_medium_rate` và `unknown rate` thực tế;
4. false positive phổ biến đã được ghi nhận;
5. quyết định được policy enrichment:
   - video nào chỉ cần Home-visible data;
   - video nào cần YouTube API metadata;
6. output luôn là multi-label Category vector + confidence + evidence.

Sau đó mới mở rộng xuống `Niche/Topic` và đưa kết quả vào Viewer Robot.
