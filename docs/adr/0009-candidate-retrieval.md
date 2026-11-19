# ADR-009: Routing Nearby/Text và phạm vi cam kết tìm kiếm theo nguồn

- **Trạng thái:** Accepted; routing và metadata có điều kiện
- **Người quyết định:** Chủ dự án FoodRadar
- **Ngày chấp thuận:** 2026-11-20
- **Giới hạn:** Không xác nhận coverage thực tế; Text Search vẫn là radius bias.
- **Ngày gốc:** 2026-11-05
- **Phạm vi:** Candidate retrieval, radius, coverage semantics
- **Liên quan:** [ADR-004](0004-google-places-provider.md), [ADR-005](0005-recommendation-strategy.md), [SRS](../product-requirements.md)

## Vấn đề

Nearby Search (New) tối đa 20 results/call, hỗ trợ `POPULARITY`/`DISTANCE` của **provider**. Text Search (New) hỗ trợ query và `locationBias.circle`, nhưng bias không giới hạn cứng trong vòng tròn; `locationRestriction.rectangle` giới hạn theo chữ nhật, không bảo đảm vòng tròn. Hậu lọc bằng tọa độ Google có rủi ro *derived content* theo điều khoản; không mặc định sử dụng. Không API nào bảo đảm tìm đủ mọi quán.

## Phương án

| Phương án | Lợi ích | Đánh đổi |
|---|---|---|
| Nearby only | Phù hợp theo type và bán kính do provider áp | Không tìm món cụ thể; max 20 |
| Text only | Tìm từ khóa/món | Bias có thể ngoài vùng, max 60 qua nhiều trang, request/cost tăng |
| **Intent-based routing** | Một call mục đích rõ | Phải minh bạch coverage và radiusPolicy |
| Nearby + Text luôn | Candidate nhiều hơn | Chi phí và thiếu đảm bảo bao phủ; không chọn |

## Quyết định

1. `sourceMode=GOOGLE_DISCOVERY`: `query` sau trim **không rỗng** => Text Search `textQuery`, `locationBias.circle`, `pageSize<=20`; không có query => Nearby Search `includedTypes` từ allowlist và `locationRestriction.circle`, `maxResultCount<=20`, `rankPreference=DISTANCE` mặc định để gần nhất theo thứ tự provider (không tính khoảng cách riêng). Mỗi API search call tối đa 1 call/user request; chưa paginate/fan-out.
2. Google mode giữ thứ tự Google trả về. **Không** hậu lọc bằng Haversine/point-in-polygon trên Places lat/lng, không tính distance hoặc custom ranking khi chưa được duyệt licensing cụ thể. Với Text: `radiusPolicy=PROVIDER_BIAS_ONLY`, `isRadiusStrict=false`; kết quả có thể ở ngoài vùng và query chứa địa danh có thể khiến Google bỏ qua location bias. Với Nearby: `radiusPolicy=PROVIDER_CIRCLE_RESTRICTION`, `isRadiusStrict=true` chỉ mô tả giới hạn vòng tròn do provider áp dụng, **không** phải FoodRadar kiểm lại tọa độ hay đã liệt kê hết nơi trong vòng tròn.
3. `sourceMode=OWNED_DATA` sử dụng PostGIS trên dữ liệu FoodRadar có quyền sử dụng: strict radius, strict filters và recommendation Strategies. `radiusPolicy=FOODRADAR_ENFORCED`, `isRadiusStrict=true`. Nếu chưa có dữ liệu owned, kết quả có thể rỗng; không backfill synthetic ở public.
4. `query + placeType`: Với Google Text Search, `query` thắng để chọn mode; `placeType` chỉ áp dụng khi được ánh xạ thành `includedType` do provider hỗ trợ và `strictTypeFiltering` được xác nhận. Trong MVP **không cho kết hợp** 2 trường với Google để tránh lọc ngầm: trả `422 UNSUPPORTED_FILTER_FOR_SOURCE` khi query có giá trị mà placeType được gửi. Nearby thì placeType optional default `restaurant`. OWNED_DATA hỗ trợ kết hợp nếu có data.
5. `openNow`, `minRating`, `minUserRatingCount` trong Google mode **không hỗ trợ** ở MVP trừ khi có phương án dùng native provider filter chính xác và quyền sử dụng đã phê duyệt; trả `422 UNSUPPORTED_FILTER_FOR_SOURCE` thay vì âm thầm bỏ hoặc hậu lọc. Với Owned mode, áp hard filters vào dữ liệu sở hữu.
6. Response metadata: `sourceMode`, `retrievalMode`, `rankingMode`, `radiusPolicy`, `isRadiusStrict`, `isExhaustive=false`, `candidateCount`, `coverageNotice`, `providerAttribution`. Không diễn giải `candidateCount` là số quán tồn tại trong vùng. Frontend phải thể hiện rõ Text là "ưu tiên gần vị trí đã chọn", không ghi "chỉ trong bán kính".
7. Gợi ý nhập/chọn vị trí thủ công trên UI bằng pin/tọa độ. Nhập chuỗi địa chỉ/Geocoding phải có ADR, pricing và policy trước khi bật.

## Logic và ví dụ

| Input | Source | Provider call | Thứ tự | Radius guarantee |
|---|---|---|---|---|
| `query=null,placeType=restaurant,r=5000` | Google | Nearby | Provider | Provider Circle, không exhaustive |
| `query="phở",placeType omitted,r=5000` | Google | Text | Provider | Location bias only, **có thể ngoài 5 km** |
| `query="phở",placeType=cafe` | Google | Không gọi | N/A | `422` tránh coupling không rõ |
| `minRating=4.3` | Google | Không gọi | N/A | `422` trước khi tính phí |
| `query="phở",minRating=4.3,r=5000` | Owned | Internal PostGIS | Strategy | Strict circle với data owned |

**Hạn chế:** `Text Search minRating` làm tròn lên bội 0.5 và không thay thế bộ lọc local yêu cầu 4.3; vì vậy không push-down ngưỡng này trong Google MVP. Text Search có thể trả tối đa 60 qua các trang (tùy thay đổi); MVP chỉ một trang/call.

## Acceptance & NFR

- Test routing, trim/blank query (blank => treat as absent), 1 outbound search call max kể cả lỗi 5xx (không auto-retry), error 422 no outbound, strict Owned Search, radius flags/copy.
- Google mode không gọi geodesic calculation trên Google candidates, không gọi ranking strategy, không hứa "top toàn khu vực".
- Monitoring: external calls by method/SKU, count, empty rate, response latency; không log tọa độ chính xác.
- Pricing, quota và legal review chặn public release khi chưa đáp ứng điều kiện.

## Khi xem xét lại

Khi có license cho Google derived processing, owned dataset đủ lớn hoặc người dùng chấp nhận phạm vi bias/candidate hạn chế; lập ADR kế tiếp và cập nhật OpenAPI cùng một release nếu thay đổi quyết định đã chấp thuận.

## Tài liệu chính thức (kiểm tra lại 2026-11-12)

- [Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
- [Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Google Terms](https://cloud.google.com/maps-platform/terms)
