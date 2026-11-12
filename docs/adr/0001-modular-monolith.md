# ADR-001: Chọn Modular Monolith thay vì Traditional Monolith và Microservices

- **Trạng thái:** Proposed (Đề xuất; chưa được phê duyệt)
- **Ngày:** 2026-11-04
- **Phạm vi:** Kiến trúc hệ thống; MVP và kế hoạch mở rộng
- **Người quyết định:** Chủ dự án FoodRadar
- **Rà soát:** 2026-11-12; đề xuất chấp thuận kiến trúc MVP sau khi chủ dự án xác nhận
- **Liên quan:** [ADR-002](0002-layered-and-ports-adapters.md), [ADR-006](0006-sync-and-async-processing.md)

## 1. Bối cảnh

FoodRadar hỗ trợ tìm quán ăn theo vị trí, bộ lọc, xếp hạng gợi ý, đăng nhập, lưu yêu thích và sở thích cá nhân. Phiên bản đầu phục vụ mục tiêu CV Backend Java Intern; về sau có thể mở rộng thành đồ án tốt nghiệp và sản phẩm thật. Đội ngũ ban đầu nhỏ, số người dùng và lưu lượng chưa được đo, hệ thống phụ thuộc Google Places API và cần kiểm soát chi phí cloud.

**Câu hỏi:** Nên triển khai toàn bộ nghiệp vụ trong một ứng dụng hay tách thành nhiều dịch vụ độc lập?

## 2. Yếu tố quyết định

1. Hoàn thiện MVP nhanh nhưng vẫn có ranh giới nghiệp vụ rõ ràng.
2. Có thể chạy và deploy trên hạ tầng hạn chế, giảm chi phí và gánh nặng DevOps.
3. Dễ thực hiện integration test, quản lý transaction và debug end-to-end.
4. Có khả năng bổ sung Recommendation Engine, nguồn quán nội bộ và analytics sau này.
5. Không tự tạo distributed-systems complexity khi chưa có bằng chứng cần thiết.

## 3. Các phương án

| Phương án | Ưu điểm | Nhược điểm | Kết luận |
|---|---|---|---|
| Traditional Monolith không kiểm soát module | Nhanh triển khai, ít thiết lập | Dễ phụ thuộc chéo và logic đan xen khi phát triển | Không chọn làm nguyên tắc kiến trúc |
| **Modular Monolith** | Một tiến trình/deploy; module theo nghiệp vụ; dễ test và refactor | Chung failure domain; không scale/deploy từng module độc lập | **Chọn** |
| Microservices | Scale và deploy từng service; tự chủ công nghệ/hạ tầng | Network failure, tracing, consistency, deployment phức tạp; overhead nhiều JVM | Hoãn tới khi có nhu cầu thực |
| Serverless nhiều function | Có thể scale theo nhu cầu, ít quản trị server | Cold start, giới hạn runtime, debugging/distributed workflow khó hơn | Không chọn cho MVP |

## 4. Quyết định

Xây dựng **một Spring Boot deployable duy nhất** theo **package-by-feature**. Mỗi business module có public API ổn định và phần implementation nội bộ. Không tạo nhiều microservice, API Gateway hay service discovery trong MVP.

Các module dự kiến:

- `identity`: xác thực, tài khoản và security policy.
- `profile`: sở thích, thông tin cá nhân, quyền quản lý dữ liệu.
- `discovery`: use case tìm địa điểm, điều phối provider và bộ lọc.
- `recommendation`: chiến lược ranking và giải thích kết quả.
- `favorites`: danh sách lưu quán, sử dụng định danh địa điểm nguồn.
- `interaction`: chỉ bổ sung sau MVP nếu có use case, consent, retention và nguồn dữ liệu hợp lệ.

Tích hợp Google Places đặt trong infrastructure của `discovery` và phơi bày qua một port, không nhất thiết tạo một business module riêng chỉ để gọi HTTP.

```text
FoodRadarApplication (1 Spring Boot process)
├── identity (public API / internal)
├── profile  (public API / internal)
├── discovery (public API / application / domain / infrastructure)
├── recommendation (public API / domain / infrastructure)
├── favorites (public API / internal)
└── interaction (sau MVP, khi có quyết định riêng)
            |
     PostgreSQL (1 logical DB)
            |
     Google Places API (external)
```

**Ranh giới bắt buộc:**

- Module A chỉ gọi public API/contract của module B; không import controller, entity, repository, mapper nội bộ của B.
- Không tạo dependency cycle giữa các module.
- Không đọc/ghi trực tiếp bảng của module khác từ repository; đi qua module API/use case được công bố.
- Mỗi module chịu trách nhiệm cho schema/tables và transaction thuộc quyền sở hữu của nó dù cùng PostgreSQL.
- Không tạo một package `common` chứa mọi business model. Chỉ chia sẻ các primitive thật sự ổn định như `PlaceReference` nếu cần.

## 5. Hệ quả

### Lợi ích
- Đơn giản hóa local development, Docker Compose, CI/CD và quan sát lỗi.
- Giao dịch nội bộ đơn giản hơn so với dịch vụ phân tán.
- Dễ triển khai luồng Google Discovery (HTTP → provider → provider-ordered response) và luồng Owned Recommendation (owned retrieval → ranking), cùng persistence cho dữ liệu FoodRadar có quyền lưu.
- Có điểm xuất phát tốt để tách module khi lưu lượng hay yêu cầu tổ chức chứng minh điều đó là cần thiết.

### Chi phí/giới hạn
- Lỗi nghiêm trọng trong một module có thể ảnh hưởng tiến trình chung.
- Không thể mở rộng riêng Recommendation Engine bằng cách tăng replica của một service tách biệt.
- Module boundary cần được **kiểm chứng bằng test và code review**; một monolith tự gắn nhãn 'modular' vẫn có thể bị coupling cao.
- Tách module thành microservice trong tương lai **không phải** thao tác tự động; cần giải quyết dữ liệu, giao tiếp mạng và consistency.

## 6. Cách triển khai và quy tắc kỹ thuật

1. Sắp xếp source theo `com.foodradar.<module>`, sau đó chia `api`, `application`, `domain`, `infrastructure` trong module cần thiết.
2. Dùng unit test cho domain, integration test theo use case và module-boundary test.
3. Có thể dùng **Spring Modulith** hoặc ArchUnit để phát hiện dependency cycle và truy cập vào internal package. Không bắt buộc thêm thư viện này nếu chưa cần, nhưng quy tắc kiểm tra phải tồn tại.
4. Trong CI: build, test, cấu trúc module, database migrations, API smoke test.
5. Tăng replica toàn bộ ứng dụng nếu khả thi trước khi cân nhắc chia service; mọi trạng thái quan trọng đặt ngoài memory của một instance.

## 7. Tiêu chí kiểm chứng (Acceptance)

Các mục dưới đây là tiêu chí kiểm chứng **triển khai**, không phải bằng chứng đã chạy ứng dụng hoặc điều kiện để đổi trạng thái ADR. Chủ dự án có thể chấp thuận quyết định thiết kế trước; kết quả kiểm thử được theo dõi ở release gate.

- `mvn test` chạy các test kiểm tra dependency boundaries, không có cycle.
- Có sơ đồ module/dependency và tài liệu các public contracts.
- Chạy ứng dụng bằng một artifact Spring Boot và một cấu hình deploy.
- Kiểm thử E2E hai luồng riêng: `Google Discovery -> provider order -> Response` (không custom ranking) và `Owned retrieval -> Ranking -> Response`; không truy cập implementation nội bộ trái ranh giới.
- Thay thế Google provider bằng stub trong integration test; thuật toán Owned Ranking không phụ thuộc Google provider.

## 8. Khi nào xem xét lại

- Recommendation cần GPU/AI inference hoặc autoscale độc lập đáng kể.
- Nhiều nhóm phát triển cần deploy với chu kỳ khác nhau.
- Một module ảnh hưởng SLO/availability của các module khác thường xuyên.
- Đã đo được bottleneck và chứng minh chỉ tăng replica toàn ứng dụng không hợp lý.

## 9. Tài liệu tham khảo

- [Spring Modulith – Verifying Application Module Structure](https://docs.spring.io/spring-modulith/reference/verification.html)
- [Spring Modulith – Project](https://spring.io/projects/spring-modulith/)

> **Kết luận:** Modular Monolith tối ưu cho phạm vi và nhân lực hiện tại, có cam kết kiểm soát coupling và đường nâng cấp có điều kiện, không mặc định sẽ chuyển sang microservices.
