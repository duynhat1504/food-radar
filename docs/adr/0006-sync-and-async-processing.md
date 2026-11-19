# ADR-006: Đồng bộ cho luồng tìm kiếm; bất đồng bộ có chọn lọc, chưa dùng message broker trong MVP

- **Trạng thái:** Accepted
- **Người quyết định:** Chủ dự án FoodRadar
- **Ngày chấp thuận:** 2026-11-20
- **Ngày:** 2026-11-04
- **Phạm vi:** Request processing, concurrency, background jobs, reliability
- **Liên quan:** [ADR-001](0001-modular-monolith.md), [ADR-004](0004-google-places-provider.md), [ADR-007](0007-redis-caching.md)

## 1. Bối cảnh

Tìm quán ăn là tương tác real-time: người dùng gửi filter và chờ danh sách kết quả. Ghi interaction, thống kê hành vi và tính toán recommendation offline là khả năng sau MVP, chỉ xem xét khi có consent, retention và mục tiêu đo rõ ràng. Hệ thống có external network I/O, nhưng chưa có bằng chứng về lưu lượng cao hoặc cần event stream lớn.

Cần **phân biệt**: (1) concurrent/asynchronous I/O giúp xử lý nhiều request hoặc nhiều external call; (2) background processing giúp tách việc phụ khỏi response; (3) durable messaging giúp không mất công việc khi process chết.

## 2. Các phương án

| Phương án | Ưu điểm | Nhược điểm | Kết luận |
|---|---|---|---|
| **Synchronous request-response** | Đơn giản, đáp ứng trực tiếp nhu cầu search | Phụ thuộc latency nhà cung cấp | **Chọn cho search MVP** |
| `CompletableFuture`/virtual threads cho I/O độc lập | Có thể rút ngắn latency nếu thật sự có nhiều call song song | Bắt buộc giới hạn concurrency, timeout, cancellation; debug khó hơn | Chỉ dùng sau benchmark |
| `@Async` in-process cho tác vụ phụ | Nhẹ, không cần broker | Không bền vững khi crash/restart, khó bảo đảm delivery | Chỉ dùng best-effort |
| Transactional outbox + worker | Có thể thực hiện công việc bền vững và retry | Thêm bảng/job/at-least-once semantics | Khi có event quan trọng |
| RabbitMQ / Kafka | Decouple và durable delivery nếu thiết kế đúng | Vận hành, idempotency, retry, tracing, DLQ | Hoãn tới khi có bài toán |

## 3. Quyết định

### 3.1. Luồng tìm kiếm đồng bộ

```text
POST /api/v1/places/search
    -> Validate + rate limit
    -> Source policy
       -> GOOGLE_DISCOVERY: Google adapter (1 search call, timeout) -> provider order
       -> OWNED_DATA: owned retrieval -> hard filters -> ranking strategy
    -> HTTP response (source + coverage metadata)
```

- Mọi external I/O có **connect/read/overall timeout** phù hợp.
- Có upper bound cho concurrent outbound calls; không tạo `new Thread()` hoặc executor vô hạn cho mỗi request.
- Trong MVP, không tự retry provider search: mọi retry có thể biến một lượt user search thành nhiều provider calls, trái giới hạn một call ở SRS. Nếu sau này thay đổi, phải sửa đồng thời ADR-004/009, cost budget và contract tests.
- Circuit breaker và bulkhead là biện pháp khi đã đo bottleneck/khả năng tràn tài nguyên.
- Không duy trì DB transaction suốt quá trình chờ HTTP từ Google.
- Không dùng queue cho search chỉ để gắn mác 'async'; queue khiến phải polling/WebSocket cho kết quả, tăng độ phức tạp.

### 3.2. Background task không ảnh hưởng user response

- Search analytics, thống kê món/quán được tìm và recommendation feature precomputation chỉ là lựa chọn sau MVP khi có consent, retention, nguồn dữ liệu hợp lệ và nhu cầu đo được.
- **Best-effort không quan trọng:** có thể dùng bounded `@Async` executor; nếu bỏ lỡ event khi server crash thì phải được chấp nhận và ghi rõ.
- **Công việc cần delivery bảo đảm:** dùng PostgreSQL transactional outbox + worker và idempotent consumer (sau MVP). Không xem `@Async` hay Spring event in-memory là durable queue.
- Ghi lịch sử mang tính tính năng cốt lõi phải được xác định: nếu user kỳ vọng lưu chắc chắn, thực hiện trong transaction DB hoặc qua cơ chế durable đáng tin.
- Event hành vi chỉ ghi khi phù hợp consent/retention, không log GPS chính xác nếu không cần.

## 4. Chịu tải và cơ chế bảo vệ

Một ví dụ 1.000 người × 3 lần search/5 phút tương đương **10 RPS trung bình**; đây không phải dự báo traffic thực. Khi external call trung bình 0,8 giây, lý thuyết Little's Law cho khoảng 8 external request đồng thời ở tải đều (`L=λW`), chưa tính burst và timeout. Vì vậy kiểm soát in-flight requests quan trọng hơn số thread theo cảm tính.

Mục tiêu kiểm thử dự kiến (sẽ hiệu chỉnh ở NFR):

- Load test 10 / 50 / 100 RPS với **stub provider**; đo p50/p95/p99, error rate, CPU/memory, pool wait.
- Tách đo latency nội bộ và end-to-end với external provider; không đặt KPI không kiểm soát được mà không có điều kiện ràng buộc.
- Test burst, timeout storm, 429 storm, circuit-open, graceful shutdown và exhausted connection pool.
- Đánh giá rate limit client theo IP/user và external call budget; quota upstream phải được bảo vệ riêng.

## 5. Quy tắc triển khai

- Dùng REST API đồng bộ với Spring MVC (sufficient for MVP).
- Dùng HTTP client có connection pooling, timeout, instrumentation; không chọn reactive stack chỉ vì có external API.
- Không truyền SecurityContext/transaction tùy tiện sang worker thread; nếu dùng async, thiết kế propagation rõ ràng.
- Thiết kế task/event ID để retry không ghi trùng khi dùng delivery at-least-once.
- Nếu dùng outbox về sau, transaction ghi domain state và outbox trong cùng DB transaction; worker poll/publish và consumer idempotent.

## 6. Hệ quả

**Lợi ích:** giảm moving parts, search flow dễ truy vết, API dễ làm Postman/E2E; vẫn có đường nâng cấp theo workload.

**Nhược điểm:** search latency chịu tác động Google; nếu analytics chạy inline có thể làm tăng latency (giải quyết bằng lựa chọn background có chủ đích); durability của `@Async` không được bảo đảm.

## 7. Tiêu chí kiểm chứng

- Đo được p95 end-to-end và thời gian call provider riêng, có timeout thực tế.
- Load test không tạo số lượng outbound connection/thread vô hạn.
- Provider fail trả lỗi có mã rõ, không giữ request treo vô thời hạn.
- Chưa có Kafka/RabbitMQ như dependency bắt buộc trong MVP.
- Nếu thêm tác vụ background, tài liệu ghi rõ **best-effort** hay **reliable** và test tương ứng.

## 8. Khi nào xem xét lại

- Analytics/event throughput tăng, nhiều consumer độc lập, cần replay hoặc durable queue.
- External enrichment có nhiều call độc lập và parallelization mang lại cải thiện đo được.
- Độ trễ search quá cao dù đã tối ưu provider/timeout/ranking.
- Có yêu cầu xử lý kéo dài không phù hợp HTTP request-response.

> **Kết luận:** 'Có chịu tải' không đồng nghĩa 'phải Kafka'. Ưu tiên giới hạn tài nguyên, timeout, resilience và benchmark trước.
