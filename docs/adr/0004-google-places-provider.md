# ADR-004: Google Places là nguồn discovery có kiểm soát, không phải kho dữ liệu FoodRadar

- **Trạng thái:** Accepted; thiết kế tích hợp có điều kiện
- **Người quyết định:** Chủ dự án FoodRadar
- **Ngày chấp thuận:** 2026-11-20
- **Giới hạn:** Live smoke, licensing, billing, attribution và public release vẫn là release gates.
- **Ngày gốc:** 2026-11-04
- **Phạm vi:** Source boundary, data rights, presentation, cost, reliability
- **Liên quan:** [ADR-002](0002-layered-and-ports-adapters.md), [ADR-003](0003-postgresql-primary-database.md), [ADR-005](0005-recommendation-strategy.md), [ADR-007](0007-redis-caching.md), [ADR-009](0009-candidate-retrieval.md)

## Bối cảnh và mục tiêu

MVP cần tìm quán ăn khi FoodRadar chưa có đủ dữ liệu sở hữu. Google Places (New) cung cấp discovery nhưng bị giới hạn bởi SKU/FieldMask, quota, số lượng candidate và điều khoản sử dụng. Việc nhận dữ liệu từ Google **không** tự cấp quyền sao chép, lập chỉ mục, tái xếp hạng bằng điểm dẫn xuất hoặc đào tạo ML từ nội dung đó. Google Maps Platform Terms §3.2.3 hạn chế *creating content from Google Maps Content*, ví dụ dùng lat/lng Places làm đầu vào cho phân tích point-in-polygon; không mặc định rằng tính khoảng cách hoặc hậu lọc không gian trên dữ liệu Google được miễn trừ.

## Phương án cân nhắc

| Phương án | Lợi ích | Đánh đổi |
|---|---|---|
| Google Places qua adapter | Có địa điểm thật để khám phá | Chi phí, quota, vendor lock-in, compliance review |
| Chỉ dữ liệu do FoodRadar sở hữu | Tự do xây ranking theo quyền dữ liệu | Cold-start, chưa có đủ quán thực |
| Dữ liệu có giấy phép khác | Có thể xây kho dữ liệu với provenance rõ | Cần kiểm tra license, attribution, coverage |
| Scraping Places/Maps | Không chọn | Rủi ro điều khoản và chất lượng dữ liệu |

## Quyết định

1. Duy trì `GoogleDiscoveryPort` và `OwnedPlaceRepository` riêng theo ADR-002. Có hai luồng tách biệt **không trộn dữ liệu tự động**:
   - `GOOGLE_DISCOVERY`: kết quả thật từ Google; giữ thứ tự do provider trả về, không tạo `foodRadarScore`, không tính `distanceMeters`/hậu lọc từ tọa độ Google theo mặc định. Trả `rankingMode=PROVIDER_ORDER`, `scoreVersion=null`, `foodRadarScore=null`; Google rating chỉ hiển thị nếu FieldMask/billing/attribution đáp ứng điều kiện.
   - `OWNED_DATA`: dùng địa điểm/menu/rating có nguồn gốc do FoodRadar sở hữu hoặc giấy phép cho phép tính toán. Cho phép PostGIS, hard filters, `DISTANCE`/`RATING`/`RELEVANCE` và `foodRadarScore`. Dữ liệu `SYNTHETIC` chỉ cho test/demo được đánh dấu; **không đưa quán giả vào public response như quán thật**.
2. `SourceReference { provider, providerPlaceId }` là ID chuẩn trong favorites, không sao chép tên/rating/toạ độ Google vào PostgreSQL. Google Place ID có ngoại lệ cache; kiểm tra refresh/lỗi ID đổi.
3. Dùng `Nearby Search` khi không có query và `Text Search` khi có query (ADR-009); Details chỉ khi user mở chi tiết. Mỗi lượt search mặc định tối đa **1 call search**; không tự paginate/fan-out.
4. Trước public beta, cần review điều khoản cho use case *restaurant discovery* (kể cả hạn chế tái tạo Google features), layout với logo/attribution, Privacy Policy/Terms, và phương án score. Nếu sau này có quyền cho thêm thao tác trên Google, phải mở ADR kế tiếp với bằng chứng/điều kiện cụ thể; **không bật tự động**.

Google Maps Platform Terms hiện hành còn hạn chế việc sửa tính toàn vẹn search results. Vì vậy `GOOGLE_DISCOVERY` không hậu lọc hoặc đảo thứ tự kết quả Google. Đây là ranh giới thiết kế thận trọng; quyết định tuân thủ cho use case cụ thể phải được ghi riêng trước phát hành.

## Data lifecycle và hiển thị

| Dữ liệu | Chính sách MVP |
|---|---|
| Google Place ID | Có thể lưu reference vào favorite; kiểm tra trạng thái ID khi lấy detail |
| Google names/rating/reviews/lat-lng/raw JSON | Không lưu dài hạn, không cache qua Redis/DB, không log payload; chỉ request-scoped theo điều khoản |
| Rating, feedback, menu, coordinates do FoodRadar/partner cung cấp hợp lệ | Lưu được với provenance và consent/retention thích hợp |
| Google Places list | Logo/attribution theo tài liệu Google; nếu có bản đồ thể hiện Places data thì dùng Google Map |
| AI training/validation | Không sử dụng Google Maps Content theo mặc định |

**Chú ý:** Chính sách cho phép lưu tọa độ tạm thời tối đa 30 ngày trong một số phạm vi **không** đồng nghĩa quyền tự do tạo nội dung dẫn xuất. Không áp dụng ngoại lệ này cho cache trong MVP.

## FieldMask và cấu hình chi phí

| API | Mặt nạ tối thiểu đề xuất | SKU dự kiến | Ghi chú |
|---|---|---|---|
| Nearby Search | `places.id,places.displayName,places.googleMapsUri,places.attributions` | Pro (kiểm chứng theo bảng hiện hành) | `displayName`, `googleMapsUri` đẩy lên Pro |
| Text Search | `places.id,places.displayName,places.googleMapsUri,places.attributions` | Pro | `textQuery` bắt buộc |
| Details | `id,displayName,googleMapsUri,attributions` | Pro | FieldMask ở root, không có `places.` |
| Search có ratings | Thêm `places.rating,places.userRatingCount` | Enterprise | **Feature gate OFF** mặc định cho đến khi budget được duyệt |

Không sử dụng `*` ở production. Có thể hiện rating khi được phép, nhưng vẫn không tạo score từ nó. Các mức giá thực phải đối chiếu trang [Pricing](https://developers.google.com/maps/billing-and-pricing/pricing) và [Data Fields](https://developers.google.com/maps/documentation/places/web-service/data-fields) trước khi bật tính phí.

**Cost guard:** Backend giới hạn call/search và concurrent outbound; Google Cloud áp quota theo API/method, budget alerts (chỉ cảnh báo, không chặn cứng), rate limit người dùng, audit count/latency/error. Ước tính chi phí theo SKU cho mỗi release. API key server-side, API restricted, không commit. Sản phẩm cần cho phép tắt Google provider bằng feature flag khi vượt ngân sách hoặc có vấn đề pháp lý.

## Failure handling

| Điều kiện | Phản hồi FoodRadar |
|---|---|
| Request không hợp lệ | `400 INVALID_SEARCH_REQUEST` |
| Client spam/rate limit | `429 CLIENT_RATE_LIMITED` |
| Google auth/key/permission | `503 PROVIDER_CONFIGURATION_ERROR`; không retry |
| Google quota/429 | `503 PROVIDER_QUOTA_EXHAUSTED`; không retry dồn dập |
| Google timeout | `504 PROVIDER_TIMEOUT` |
| Google 5xx | `502 PROVIDER_BAD_GATEWAY`; không tự retry search trong MVP để giữ giới hạn một provider search call |
| Google 0 candidates | `200` mảng rỗng, `isExhaustive=false` |

Không tự thay Google results bằng synthetic data. Nếu có licensed owned data và explicit fallback, trả riêng cùng `sourceMode`/notice; không âm thầm trộn provider.

## Kiểm chứng / Acceptance

Việc chủ dự án chấp thuận ADR chỉ xác nhận ranh giới tích hợp nêu trên. Các mục dưới đây là release/implementation gates độc lập và vẫn mở cho đến khi có bằng chứng thực tế.

- Contract tests với stub: FieldMask, no wildcard, route selection, bounded calls, error mapping, blank/missing fields, redaction.
- API live smoke: 1 Nearby + 1 Text + 1 Details sau khi có billing/quota/key; không log Places payload; ghi billing quan sát theo console.
- `GOOGLE_DISCOVERY` response **không có** derived score/distance/filter; preserve provider order; không dùng Google DTO trong domain recommendation.
- UI kiểm tra Google branding và third-party attribution, Privacy Policy/Terms trước public.
- Cần có review ghi lại **legal/provider licensing decision** trước khi mở custom Google ranking hoặc strict circle filtering từ Google coordinates.

## Điều kiện xem xét lại

Chi phí/quota vượt ngân sách, provider đổi chính sách, đủ owned dataset, hoặc nhận được xác nhận quyền dùng cụ thể (theo use case và lãnh thổ).

## Nguồn chính thức (kiểm tra lại 2026-11-12)

- [Places API Policies](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms)
- [Google Maps Platform Service Specific Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms)
- [Place Data Fields](https://developers.google.com/maps/documentation/places/web-service/data-fields)
- [Pricing](https://developers.google.com/maps/billing-and-pricing/pricing)

> Review này là đánh giá kỹ thuật nhằm giảm rủi ro, không thay thế quyết định pháp lý/giấy phép từ Google.
