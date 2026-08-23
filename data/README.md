# Runtime data workspace

`data/` là vùng dữ liệu runtime do code tự tạo và tự đọc. Repository không track raw/intermediate/profile/report files trong thư mục này.

Các nhóm dữ liệu có thể xuất hiện khi chạy hệ thống:

```text
data/
├── android_ingest/          # raw Android Accessibility snapshots nhận từ server ingest
├── browser_ingest/          # đích dự kiến cho raw browser snapshots sau khi Chrome push trực tiếp
├── home_snapshots/          # legacy/local browser evidence
├── up_next_snapshots/
├── subscriptions_snapshots/
├── *_enriched/              # metadata enrichment trung gian
├── *_classified/            # classification trung gian
├── collection_sessions/     # session state trung gian
├── profile_library/         # longitudinal profile machine state
├── community_profiles/      # sanitized current profile state tại central
├── community_reports/       # creator output
├── android_snapshots/       # ADB/debug fixtures; không phải transport chính
└── synthetic_viewers/       # sandbox simulation, không phải ground truth
```

Không thư mục nào ở trên cần tồn tại sẵn trong Git; code phải `mkdir` khi cần.

## Dữ liệu dành cho máy và dữ liệu dành cho người dùng

Phần lớn JSON/JSONL là **machine-readable state** cho parser, classifier, profile engine và aggregator. Người dùng không cần mở chúng để vận hành hệ thống.

Đầu ra chính cho creator là:

```text
data/community_reports/current.html   # UI chính
data/community_reports/current.json   # machine/API representation của cùng kết quả
```

Các report theo từng profile/raw snapshot chỉ là debug/provenance và không phải giao diện sản phẩm chính.

## Nguyên tắc

- Raw participant evidence không commit lên GitHub.
- Token, identity local, cookies/session data không commit.
- Central analysis có thể giữ raw/intermediate theo retention policy của deployment.
- Creator Dashboard chỉ dùng dữ liệu đã qua normalize/classify/profile/aggregate.
