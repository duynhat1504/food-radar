# FoodRadar – Software Requirements Specification (SRS v1.0 – Proposed)

- **Cập nhật:** 2026-11-12 · **Trạng thái:** Proposed; chưa chấp thuận công khai
- **Nguồn sự thật cho API:** [OpenAPI](openapi.yaml)
- **Kiến trúc:** [ADR-001–009](adr/README.md)
- **Phạm vi:** HCMC pilot, web-first, guest discovery; identity & favorites; ranking có quyền dữ liệu rõ ràng.

## 1. Phạm vi MVP đã chốt để thiết kế

**Mục tiêu cho CV:** Backend Spring Boot có search facade, Google provider adapter, error handling, auth, preferences/favorites, integration tests, CI/CD, đo hiệu năng với stub; có offline recommendation demo trên synthetic hoặc dữ liệu có giấy phép; triển khai khi policy/billing đáp ứng.

**Luồng A – Google Discovery (public candidate, vẫn cần release gates):** User xác định tọa độ (GPS hoặc pin thủ công), chọn bán kính 100–10.000 m, tìm loại quán bằng Nearby hoặc từ khóa bằng Text, xem danh sách chi tiết có nguồn/attribution và lưu favorite. Giữ thứ tự provider; **không có foodRadarScore, khoảng cách do FoodRadar tính hoặc strict Text circle**. `googleRating` chỉ là dữ liệu hiển thị nếu FieldMask/SKU có quyền và chi phí được duyệt.

**Luồng B – Owned Recommendation (development + khi có dataset thật hợp lệ):** User tìm các quán trong tập dữ liệu sở hữu/được cấp phép; backend lọc bán kính nghiêm ngặt, lọc rating/openNow và chạy Strategy `DISTANCE`, `RATING`, `RELEVANCE`. Dùng dataset synthetic riêng biệt cho test/demo offline, không gắn nhãn là quán thực và không phân phối trong public production.

**Giới hạn lời hứa sản phẩm:** Luồng A là discovery theo thứ tự Google, chưa phải gợi ý cá nhân hóa do FoodRadar tính. Luồng B mới đáp ứng strict radius và custom ranking, nhưng cần dataset quán thật đủ quyền trước khi cung cấp cho public. Nếu chưa có dataset đó, không quảng bá MVP là "AI đề xuất quán thật phù hợp trong bán kính". Với Google Text, UI ghi "ưu tiên gần vị trí đã chọn" vì kết quả có thể ngoài bán kính; query có địa danh có thể khiến location bias bị bỏ qua.

**Bị loại khỏi MVP:** menu giá món chính xác, đặt bàn/đặt món, social reviews, NLP AI, học máy từ Google Maps Content, auto-pagination, geocoding chuỗi địa chỉ, message queue, Redis bắt buộc, công khai số điểm FoodRadar bắt nguồn từ Google data.

**Hướng AI sau MVP:** Ưu tiên parser tiếng Việt chuyển câu người dùng thành bộ lọc có cấu trúc để họ kiểm tra/sửa. Thiết kế endpoint, schema, privacy, chi phí và fallback trong ADR/API contract riêng trước khi bật. Không dùng Google Maps Content làm đầu vào AI hoặc tập huấn luyện/đánh giá.

## 2. Actors / hành trình

- **Guest:** cấp GPS tùy chọn hoặc chọn vị trí trên bản đồ, xem Google Discovery, mở Details (với logo/attribution phù hợp). Không ghi lịch sử hoặc analytics hành vi mặc định.
- **Registered User:** như Guest, thêm đăng nhập, xem/cập nhật preferences, lưu và xóa favorite, xóa tài khoản.
- **Operator:** cấu hình cost budget, quota, FieldMask, feature flags; xem metrics không chứa vị trí chính xác; tắt provider khi sự cố.
- **Developer/Research:** chạy ranking `OWNED_DATA` trên synthetic hoặc licensed dataset; không dùng Google Content để train/test/validate AI.

## 3. Functional requirements

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| FR-LOC-01 | GPS tùy chọn và pin thủ công | GPS denied vẫn dùng được; client gửi lat/lng do user chọn; không lưu vị trí mặc định |
| FR-LOC-02 | Radius validation | `radiusMeters` trong [100,10000], lat [-90,90], lng [-180,180]; `400` nếu sai |
| FR-SEARCH-01 | Google Nearby | `query` absent/blank -> Nearby, mặc định restaurant; 1 search call, `maxResultCount<=20`, provider rank=DISTANCE mặc định; không claim exhaustive |
| FR-SEARCH-02 | Google Text | `query` sau trim nonblank -> Text, `pageSize<=20`, `locationBias` chỉ là bias, không claim strict circle |
| FR-SEARCH-03 | Không bỏ lọc âm thầm | Google mode có `minRating`, `minUserRatingCount`, `openNow=true`, hoặc `query+placeType` -> `422` *trước khi gọi provider* |
| FR-SEARCH-04 | Metadata trung thực | Response có `sourceMode`, `retrievalMode`, `radiusPolicy`, `isRadiusStrict`, `isExhaustive`, `coverageNotice`, `candidateCount` |
| FR-SEARCH-05 | Google display | Kết quả giữ provider order; không `foodRadarScore`/`distanceMeters`/`reasons` do FoodRadar tạo; dùng logo/attributions |
| FR-SEARCH-06 | Owned search | Khi enabled có licensed dataset: PostGIS strict radius + strict filters + 3 ranking modes; không trả quán synthetic như quán thật |
| FR-DETAIL-01 | Details | Chỉ gọi Google Details khi user mở; lưu reference ID, không lưu Place payload |
| FR-AUTH-01 | Đăng ký/đăng nhập | Email normalized unique; password hash mạnh; JWT access; auth errors không leak email existence |
| FR-AUTH-02 | Refresh/logout | Rotate refresh token có lưu hash và revoke; request invalid/replayed -> 401, revoke session; security policy sẽ chi tiết ở LLD |
| FR-PROFILE-01 | Preferences | GET/PUT preferences theo user auth, schema allowlist, không có dữ liệu Google |
| FR-FAV-01 | Favorites | Auth required, GET/POST/DELETE; unique(user,provider,providerPlaceId), không lưu Google attributes |
| FR-ACCOUNT-01 | Xóa tài khoản | Auth required; xóa/ẩn danh dữ liệu cá nhân theo chính sách retention và confirm hành động |
| FR-ERROR-01 | Provider failures | `429 CLIENT_RATE_LIMITED`, `503 PROVIDER_QUOTA_EXHAUSTED`, `504 PROVIDER_TIMEOUT`, `502 PROVIDER_BAD_GATEWAY`; không fake fallback |
| FR-COST-01 | Mỗi search tối đa 1 provider search call | Không auto-retry provider search kể cả 5xx trong MVP; record call count, disable provider khi budget/quota gate |

**Ngoài scope:** Feedback API đã có ở draft trước được chuyển sang post-MVP; không có trong hợp đồng MVP v1. Hỗ trợ tìm kiếm free-text và `placeType` cùng lúc ở Google cũng chưa bật, sẽ có test 422 rõ ràng.

## 4. Business rules và mode matrix

| Attribute | GOOGLE_DISCOVERY | OWNED_DATA |
|---|---|---|
| rankingMode | `PROVIDER_ORDER` (default và duy nhất) | `RELEVANCE` default; `DISTANCE`/`RATING` |
| radiusPolicy khi Nearby | `PROVIDER_CIRCLE_RESTRICTION` | N/A |
| radiusPolicy khi Text | `PROVIDER_BIAS_ONLY` (có thể ngoài bán kính) | N/A |
| radiusPolicy owned | N/A | `FOODRADAR_ENFORCED` |
| `foodRadarScore` | null/omitted | 0..1 với relevance; null với distance/rating |
| `distanceMeters` | Không trả, không tính | Khoảng cách thẳng tính trên owned coords |
| `minRating`/`minUserRatingCount`/`openNow` | 422 nếu dùng | Strict, unknown fails hard filter |
| `query + placeType` | 422 | Có thể hỗ trợ nếu licensed menu/type data |
| Coverage | `isExhaustive=false` | Chỉ đầy đủ trong **tập owned đã index**, không phải mọi quán trong thành phố |

Quy định input: `query` trim; blank -> treated as absent (Nearby). `query` dài >120 -> 400. `placeType` allowlist; default restaurant khi Nearby. Request có field không hỗ trợ => 422 với `fieldErrors`; không silently ignore.

## 5. Data model (logical)

`users`, `refresh_sessions` (chỉ hash token), `user_preferences`, `favorite_places`; sau MVP có `recommendation_feedback`, `owned_places`, `menus` nếu nguồn được phép. `UNIQUE(user_id,provider,provider_place_id)`; `UNIQUE(users.normalized_email)`; Flyway migration. Không tạo bảng Google search snapshots. Google ID có thể thay đổi/unavailable; Favorites detail là live lookup và có trạng thái unavailable.

## 6. Non-functional requirements (mục tiêu thử nghiệm, chưa đo đạt)

| ID | Mục tiêu | Cách đo |
|---|---|---|
| NFR-PERF-01 | Internal search with provider stub: mục tiêu thử nghiệm p95 < 300ms ở 50 RPS | k6, ghi cấu hình máy, synthetic fixtures, duration, error-rate |
| NFR-PERF-02 | Google provider real latency đo riêng, **không** cam kết p95 khi chưa có live | Bounded smoke trên API được cấp quyền |
| NFR-SEC-01 | TLS, JWT authz, password hash, request validation, protected Google key, origin/CORS policy | Contract+security test |
| NFR-RELIAB-01 | Total request deadline, per-call timeout, bulkhead; không retry provider search ở MVP | Stub timeout/quota/failure tests |
| NFR-COST-01 | Max 1 Google search call/user search, daily/monthly quota được set theo kế hoạch, alerts bật | Metrics + Google Console quota/bill audit |
| NFR-OBS-01 | Request id, structured logs không raw Google payload, không GPS precise, request counts by provider | Log audit |
| NFR-PRIV-01 | Opt-in analytics off mặc định, account deletion và document retention | Privacy checklist + deletion integration test |
| NFR-COMP-01 | Logo/attribution, Terms/Privacy và license use-case review trước public | Manual legal/UX release gate |

**Chưa chốt:** production monthly budget hard amount, traffic forecast, performance SLA. Billing alerts **không phải** cơ chế tự chặn chi phí; giới hạn quota + backend budgets là lớp riêng.

## 7. Error/response semantics

`400` malformed fields, `401` unauthenticated, `403` forbidden, `404` resource not found, `409` favorite conflict, `422` logically unsupported source+filter combination, `429` client limit, `502` provider bad gateway, `503` provider quota/disabled/config, `504` provider timeout. Response JSON với `code`, `message`, `requestId`, optional `fieldErrors` và `retryAfterSeconds` nếu thích hợp. 0 candidates => `200` và [] thay vì 404.

## 8. Release gates và rủi ro

**Thiết kế/LLD với stub:** GO. **Live Google integration:** NO-GO trước khi key/project, API restriction, quota, billing, operator confirmation. **Public beta:** NO-GO trước khi xác nhận use-case licensing (bao gồm việc tái tạo features), attribution/UI, Privacy Policy, Terms, xóa dữ liệu, budget, smoke report và tests.

- Gate G1: ADR-004/005/009 cập nhật và trace API/SRS.
- Gate G2: Provider stub tests/contract passed, no violations in Google mode.
- Gate G3: Google live Nearby/Text/Details bằng restricted key, có số liệu redacted/billing kiểm chứng.
- Gate G4: Legal/provider approval cụ thể + UI/Privacy/Cost trước public.
- Gate G5: Muốn công bố gợi ý cá nhân hóa trên quán thật phải có dataset owned/licensed đủ coverage, provenance và kết quả đánh giá độc lập; demo synthetic không đạt gate này.

## 9. Traceability

| Design decision | Requirements | OpenAPI |
|---|---|---|
| ADR-004 | FR-SEARCH-05, FR-DETAIL-01, FR-COST-01 | `/places/search`, `/places/{provider}/{placeId}` |
| ADR-005 | FR-SEARCH-06 | `rankingMode`, `foodRadarScore`, `scoreVersion` |
| ADR-009 | FR-SEARCH-01..04 | `retrievalMode`, `radiusPolicy`, `isExhaustive` |
| ADR-003 | FR-FAV-01, FR-PROFILE-01 | favorites/preferences |
| ADR-006 | FR-ERROR-01, NFR-RELIAB-01 | errors 429/502/503/504 |

## 10. Tài liệu

- [Places Policies](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
- [Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms)

> Đây là bản SRS v1 đề xuất cho thiết kế và kiểm thử; chưa phải cam kết hiệu năng, giấy phép hay chấp thuận triển khai public.
