# Data directories

- `home_snapshots/`: lưu JSON snapshot lấy từ YouTube Home bằng `scripts/homepage/export_homepage.js`.
- `home_classified/`: lưu kết quả phân loại sinh bởi `scripts/classification/classify_homepage.py`.

Ví dụ chạy:

```bash
python scripts/classification/classify_homepage.py data/home_snapshots/home_001.json --output data/home_classified/home_001.json
```

Lưu ý: Git không lưu thư mục rỗng, vì vậy `.gitkeep` được dùng để giữ cấu trúc thư mục trong repository.
