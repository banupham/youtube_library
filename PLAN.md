# /plan — YouTube Library canonical checkpoint

> Cập nhật: 2026-08-23
>
> Kiến trúc vận hành ưu tiên tối giản: **2 phía, 1 central process, 1 external port**.

# 1. Product goal

YouTube Library thu recommendation/affinity evidence thật từ participant tự nguyện trên Chrome/Android, tạo profile theo thời gian, rồi tổng hợp thành Creator Community Intelligence.

Creator cuối cùng cần thấy:

```text
Participants / Profiles / Usable profiles
Top content opportunities
Participant/profile coverage
Core keywords / tags
Expansion keys đang rising/emerging/revived
Top intent / format
Recommended Anchor
Recommended Bridge
Controlled Expansion
Certainty / limitations
```

Không gọi coverage/opportunity score là xác suất YouTube recommendation, impression hoặc view.

# 2. Canonical architecture

```text
PARTICIPANTS
Chrome + Android
      ↓
CENTRAL SERVER :8770
      ↓
ingest → normalize → enrich → classify
→ temporal profile → participant-balanced aggregate
      ↓
CREATOR DASHBOARD
```

## Participant side

### Chrome

```text
browser_extension/youtube_home_collector/
```

Current version: `0.6.2`.

Passive collector auto-on khi participant truy cập YouTube và chỉ quan sát natural navigation:

```text
Home
Watch-page Up Next
Subscriptions / Channels
```

Không auto-click/play/like/comment/subscribe.

Chrome gửi trực tiếp vào central server `127.0.0.1:8770`.

### Android

```text
android_collector/
```

Current source version: `0.2.0`.

AccessibilityService chỉ giới hạn package:

```text
com.google.android.youtube
```

App có Server URL / Project token / Participant ID / Profile slot / Auto sync. Snapshot được lưu local trước, queue nếu lỗi mạng rồi retry tới:

```text
POST /v1/android/snapshot
```

ADB/CMD chỉ còn debug/fixture fallback.

# 3. Single central runtime

Chỉ chạy:

```bat
python scripts\community\community_server.py
```

Default:

```text
http://127.0.0.1:8770
```

Không còn `scripts/homepage/home_bridge.py`.
Không còn server phụ `8765`.
Không spawn/proxy một HTTP process khác.

Chrome analysis logic nằm trong:

```text
scripts/community/browser_pipeline.py
```

Central server gọi trực tiếp:

```text
BrowserPipeline.collect()
BrowserPipeline.finalize()
```

Endpoints:

```text
GET  /                    Creator Dashboard
GET  /dashboard            Creator Dashboard alias
GET  /profile/<id>         Browser profile HTML
GET  /health               JSON status
POST /collect              Chrome raw surface
POST /finalize             Chrome temporal profile update
POST /v1/android/snapshot  Android raw ingest
POST /v1/profile           Sanitized analyzed profile
```

# 4. Central analysis pipeline

```text
raw browser/android evidence
        ↓
platform normalization
        ↓
YouTube metadata enrichment
        ↓
content + intent classification
        ↓
per-profile daily evidence
        ↓
Today / 7d / 30d / Long-term
        ↓
baseline / emerging / rising / stable / cooling / dormant / revived
        ↓
longitudinal profile
        ↓
participant-balanced community aggregation
        ↓
creator opportunity report
```

Existing modules:

```text
scripts/community/browser_pipeline.py
scripts/community/community_server.py
scripts/community/build_community_report.py
scripts/classification/
scripts/enrichment/
scripts/profile/
taxonomy/
schemas/
```

# 5. Participant balancing

Một participant có thể có nhiều profiles/devices nhưng vẫn chỉ có một tổng community weight.

```text
Participant A
├── Browser A1
├── Browser A2
└── Android A3

Participant B
└── Browser B1
```

Không coi ví dụ trên là 4 independent humans.

# 6. Human-facing UI

Creator mở:

```text
http://127.0.0.1:8770/
```

Manual Chrome collection sau finalize tự mở:

```text
http://127.0.0.1:8770/profile/<id>
```

Raw/intermediate/profile JSON là machine data. Creator không cần đọc chúng.

Primary report runtime:

```text
data/community_reports/current.html
```

Machine/API representation:

```text
data/community_reports/current.json
```

# 7. Data policy

`data/` là runtime-only workspace. Git chỉ giữ `data/README.md`; code tự tạo folders khi cần.

# 8. Current status

```text
Chrome passive collector                    IMPLEMENTED 0.6.2
Chrome single-central transport :8770       IMPLEMENTED
Chrome in-process BrowserPipeline           IMPLEMENTED
Legacy home_bridge.py                       REMOVED

Android Accessibility collector source      IMPLEMENTED 0.2.0
Android auto sync                           IMPLEMENTED
Android raw central ingest                  IMPLEMENTED
Android APK build                           CURRENT ISSUE — FIX/VERIFY CI
Android node → normalized video parser       PENDING REAL FIXTURES
Android longitudinal profile                 PENDING PARSER

Central server single process               IMPLEMENTED v2.0
Participant-balanced aggregator             IMPLEMENTED
Creator dashboard served at /               IMPLEMENTED initial UI
Synthetic Viewer Robot                      SANDBOX ONLY
```

# 9. Immediate next engineering sequence

```text
1. Fix Android GitHub Actions APK build until artifact is green.
2. Install Android build and collect real auto-synced node fixtures.
3. Build fixture-tested Android node → normalized Home/Watch/Subscriptions parser.
4. Feed normalized Android evidence into the same profile/community pipeline.
5. Improve Creator Dashboard UI while keeping raw/intermediate data hidden.
6. Add central retention/cleanup policy for raw/intermediate runtime data.
```

# 10. Safety / interpretation boundary

- Collectors measure natural participant use; they do not create traffic/engagement.
- Chrome/Android do not auto-click/play/like/comment/subscribe.
- Android Accessibility is restricted to YouTube package.
- Community identity does not need Google email/password/cookie.
- Multiple profiles from one participant do not count as independent humans.
- Synthetic viewer is not ground truth.
- Community coverage/opportunity is panel evidence, not YouTube internal probability.

# 11. Continuation prompt

> Đọc `README.md` và `PLAN.md`. Runtime đã được rút còn một `community_server.py` trên port 8770; `home_bridge.py` đã xóa và Chrome profile logic nằm trong `browser_pipeline.py`. Creator dashboard ở `/`, profile report ở `/profile/<id>`. Tiếp tục ưu tiên fix Android APK build và Android parser.
