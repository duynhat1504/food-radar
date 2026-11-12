# FoodRadar – Architecture Decision Records (ADR)

**Dự án:** FoodRadar – Location-Based Restaurant Discovery & Recommendation  
**Mục tiêu:** MVP cho CV Backend Java Intern, có hướng phát triển đồ án tốt nghiệp và sản phẩm thực tế  
**Ngày khởi tạo:** 2026-11-04; rà soát nội dung 2026-11-12  
**Trạng thái bộ ADR:** Dự thảo để chủ dự án xem xét; chưa phải quyết định đã phê duyệt.

## Tại sao có ADR?

ADR ghi lại **lý do** quyết định kỹ thuật, không chỉ 'đã dùng công nghệ gì'. Mỗi ADR chứa Context, Decision Drivers, Alternatives, Decision, Consequences, Validation và Revisit Triggers. ADR là tài liệu ngắn, có thể review và giữ lịch sử khi kiến trúc thay đổi.

## Danh sách ADR

| Mã | Quyết định | Ưu tiên | Trạng thái |
|---|---|---|---|
| [ADR-001](0001-modular-monolith.md) | Modular Monolith thay vì microservices | MVP | Proposed |
| [ADR-002](0002-layered-and-ports-adapters.md) | Layered + Ports & Adapters chọn lọc | MVP | Proposed |
| [ADR-003](0003-postgresql-primary-database.md) | PostgreSQL làm database chính | MVP | Proposed |
| [ADR-004](0004-google-places-provider.md) | Google Places (New) là external provider | MVP | Proposed |
| [ADR-005](0005-recommendation-strategy.md) | Strategy Pattern cho ranking | MVP khi >=2 modes | Proposed |
| [ADR-006](0006-sync-and-async-processing.md) | Sync search, async có chọn lọc | MVP | Proposed |
| [ADR-007](0007-redis-caching.md) | Không dùng Redis trong MVP; cache eligibility cho giai đoạn sau | MVP / khi có nhu cầu | Proposed |
| [ADR-008](0008-rule-based-before-ai.md) | Rule-based trên owned data; AI parse sau MVP | MVP và giai đoạn sau | Proposed |
| [ADR-009](0009-candidate-retrieval.md) | Chọn Nearby Search hoặc Text Search theo ý định | MVP | Proposed |

Tài liệu liên quan: [Sơ đồ kiến trúc](../architecture-overview.md) · [SRS dự thảo](../product-requirements.md) · [OpenAPI](../openapi.yaml) · [Dữ liệu và quyền riêng tư](../data-and-privacy.md) · [Kế hoạch đánh giá](../recommendation-evaluation.md).

## Quy trình xử lý trạng thái

- **Proposed:** Đang đề xuất; có thể sửa.
- **Accepted:** Chủ dự án đã chấp thuận và nhóm triển khai theo ADR.
- **Superseded:** Bị thay thế bằng ADR mới, giữ nguyên ADR cũ và gắn link thay thế.
- **Deprecated:** Không còn áp dụng; giữ lại để tra cứu.
- **Rejected:** Phương án đã được cân nhắc nhưng không chấp nhận.

Không sửa âm thầm rationale của ADR đã Accepted; nếu thay đổi quyết định quan trọng, tạo ADR mới để giữ lịch sử.

**Phê duyệt thiết kế khác với hoàn thành triển khai/phát hành.** Khi chủ dự án quyết định, cập nhật `Trạng thái`, `Người quyết định`, `Ngày chấp thuận`, phạm vi và điều kiện còn mở trong từng ADR; ghi cùng quyết định ở bảng này. Không tự đổi `Accepted` chỉ vì tài liệu đã được sửa, test offline đã qua hoặc có kết quả live smoke. [Release readiness](../release-readiness.md) theo dõi bằng chứng triển khai và điều kiện public riêng.

## Đề xuất xử lý từng ADR sau rà soát 2026-11-12

| ADR | Đề xuất để chủ dự án quyết định | Điều kiện/giới hạn cần ghi nhận |
|---|---|---|
| 001 | Chấp thuận modular monolith | `interaction` ngoài MVP; boundary test là việc triển khai |
| 002 | Chấp thuận layered + ports chọn lọc | Port Google và owned riêng; không đưa Google DTO vào ranking |
| 003 | Chấp thuận PostgreSQL + Flyway | Schema MVP chỉ có identity/profile/favorites; PostGIS khi có owned data |
| 004 | Chấp thuận thiết kế Google Discovery có điều kiện | Không đồng nghĩa licensing, billing, attribution hay public release đã đạt |
| 005 | Chấp thuận baseline ranking trên owned/licensed data | Không bật public recommendation quán thật khi chưa có dataset hợp lệ |
| 006 | Chấp thuận search đồng bộ, không tự retry search | Background analytics ngoài MVP |
| 007 | Chấp thuận quyết định không dùng Redis trong MVP | Bổ sung Redis sau này cần use case và số liệu riêng |
| 008 | Chấp thuận sau khi xác nhận AI parser thuộc giai đoạn sau MVP | Google chỉ provider order; ví dụ score thuộc owned demo |
| 009 | Chấp thuận routing Nearby/Text và metadata | Text là bias, không bảo đảm strict radius hay coverage đầy đủ |

Các quyết định sản phẩm còn cần chủ dự án chốt: có dùng dataset quán thật đủ quyền để cung cấp recommendation public hay chỉ demo offline; UI Google hiển thị danh sách hay trên Google Map; ngân sách/quota và mục tiêu phát hành. Trước khi có những quyết định này, ADR vẫn có thể được chấp thuận **theo phạm vi thiết kế ghi rõ**, còn release gate giữ trạng thái mở.

## Những nguyên tắc đã phản ánh trong SRS v1

1. **Nguồn dữ liệu:** Google Places là external source, không mặc định được persist/caching toàn bộ content. Nguồn dữ liệu nội bộ sau này phải có provenance/quyền sử dụng rõ ràng.
2. **Phạm vi tìm kiếm:** Nearby Search (New) trả tối đa 20 candidate mỗi request; Text Search có phân trang nhưng MVP chỉ lấy một trang, dùng location bias và **không** hậu lọc tọa độ Google theo vòng tròn khi chưa có quyền sử dụng phù hợp. 'Rating cao nhất trong 10 km' không bảo đảm tính bao phủ toàn khu vực.
3. **Giá & menu:** Google price level/price range không thay thế menu giá thực. Không thiết kế strict filter 'dưới 70k' như một lời hứa có thể kiểm chứng nếu dữ liệu thiếu.
4. **Kiến trúc:** Modular Monolith có boundary; không tạo microservices/queue vì mục đích trình diễn công nghệ.
5. **Async/reliability:** Search đồng bộ, không tự retry provider search trong MVP; side tasks chỉ async khi có semantics rõ. `@Async` không bảo đảm durable delivery.
6. **Chịu tải:** Đặt mục tiêu đo có môi trường benchmark và stub provider; chưa cam kết số RPS/latency từ giả định.
7. **Bảo mật/quyền riêng tư:** Định nghĩa việc sử dụng GPS, consent cho event, thời hạn lưu và xóa dữ liệu trước khi public production.
8. **Chất lượng:** Phân biệt Google rating, số lượt đánh giá và FoodRadar score; chỉ dùng review text khi có lý do sản phẩm, chi phí và quyền dùng rõ ràng.

## Ma trận quyết định / trade-offs

| Quyết định | Lợi ích nhận được | Chi phí/chấp nhận đánh đổi | Dấu hiệu cần đánh giá lại |
|---|---|---|---|
| Modular Monolith | Đơn giản vận hành | Không scale module độc lập | Workload/tổ chức đòi hỏi độc lập |
| Layered + Ports | Tách business/vendor | Thêm interface và mapper | CRUD module quá nhỏ hoặc domain phức tạp tăng |
| PostgreSQL | Quan hệ, constraint, PostGIS roadmap | Migration và quản trị DB | Đặc thù workload analytics/search khác đi |
| Google Places | Dữ liệu ngay cho MVP | Quota, chi phí, license, coverage | Quá tốn/thiếu giá/nguồn owned mạnh hơn |
| Strategy | Test và đổi thuật toán | Thêm class/abstraction | Chỉ còn 1 ranking mode |
| Sync search | Dễ hiểu và đo được | Chờ provider | Workload dài hoặc nhiều tác vụ độc lập |
| Conditional Redis | Giảm DB latency của owned data | Stale/invalidation/ops | Hit ratio thấp hoặc policy thay đổi |
| Rule-based | Giải thích/test dễ | Cá nhân hóa hạn chế | Có dữ liệu và đánh giá ML tốt hơn |

## Việc cần phê duyệt/kiểm chứng thêm (không tự giả định)

- Bản đồ frontend sử dụng Google Maps hay danh sách thuần; yêu cầu attribution/giấy phép tương ứng.
- API quota/budget hàng tháng, độ trễ chấp nhận được, mức người dùng mục tiêu và môi trường deploy.
- Bán kính MVP theo SRS v1 là 100 m–10 km; đánh giá lại ngưỡng bằng thử nghiệm người dùng trước khi triển khai công khai.
- Yêu cầu account bắt buộc hay cho phép guest search; consent và data deletion.
- Với địa điểm nội bộ: ai được nhập/cập nhật menu, cần xác minh chủ quán ra sao.
- Mốc nào triển khai PostGIS với dữ liệu owned; Redis không thuộc MVP và chỉ xét lại khi có số liệu.

## Tài liệu tham khảo gốc

- [Google Places Nearby Search (New)](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
- [Google Places policies & attribution](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Places Place IDs](https://developers.google.com/maps/documentation/places/web-service/place-id)
- [Google Maps Places API pricing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)
- [Spring Modulith module verification](https://docs.spring.io/spring-modulith/reference/verification.html)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [PostGIS ST_DWithin](https://postgis.net/docs/ST_DWithin.html)

**Tuyên bố:** Đây là tài liệu kỹ thuật phục vụ quyết định thiết kế, không phải tư vấn pháp lý. Cần kiểm tra điều khoản/API, giá và giới hạn tại thời điểm triển khai.


## Đồng bộ Phase 0 và rà soát 2026-11-12

Mọi ADR đã được rà soát theo hai luồng `GOOGLE_DISCOVERY` và `OWNED_DATA`. Chính sách nguồn chuẩn là ADR-004 cùng [SRS](../product-requirements.md). Không có ADR nào tự cấp quyền score/cache Google Content. Tất cả vẫn `Proposed` chờ quyết định của chủ dự án.
