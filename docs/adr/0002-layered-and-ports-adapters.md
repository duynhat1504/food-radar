# ADR-002: Layered Architecture trong module; Ports & Adapters ở ranh giới bên ngoài

- **Trạng thái:** Proposed
- **Rà soát:** 2026-11-12; đề xuất chấp thuận ranh giới module sau khi chủ dự án xác nhận
- **Ngày:** 2026-11-04
- **Phạm vi:** Kiến trúc mã nguồn, dependency và testability
- **Liên quan:** [ADR-001](0001-modular-monolith.md), [ADR-004](0004-google-places-provider.md), [ADR-005](0005-recommendation-strategy.md)

## 1. Bối cảnh

FoodRadar có phần nghiệp vụ thay đổi thường xuyên (filter, scoring) và phần hạ tầng dễ biến động (Google Places DTO, HTTP client, database). Nếu controller gọi thẳng Google API/JPA và xếp hạng trong cùng một class, thay đổi provider sẽ lan sang domain và kiểm thử khó cô lập.

## 2. Các phương án

| Phương án | Ưu điểm | Bất lợi | Mức phù hợp |
|---|---|---|---|
| Controller–Service–Repository thuần | Đơn giản, rất quen với Spring Boot | Service dễ phình to; domain lệ thuộc HTTP/JPA nếu thiếu kỷ luật | Phù hợp CRUD đơn giản |
| **Layered + Ports & Adapters có chọn lọc** | Rõ trách nhiệm, cô lập external dependency; vừa phải số class | Phải tạo interface/mapper tại ranh giới quan trọng | **Chọn** |
| Full Clean Architecture cho mọi use case | Testability/independence cao | Nhiều tầng, mapping, interface; chậm MVP | Không áp dụng máy móc |
| Full Hexagonal toàn ứng dụng | Port/adapters nhất quán | Overengineering nếu mọi repository/use case đều bị bọc nhiều tầng | Chưa cần |

## 3. Quyết định

Bên trong các module có nghiệp vụ thực, tổ chức theo bốn vai trò:

1. **`api/`**: REST controller, request/response DTO, validation; không chứa business rules.
2. **`application/`**: orchestration use case, giao dịch dữ liệu, authorization theo use case; định nghĩa outbound ports cần thiết.
3. **`domain/`**: invariant, scoring, policy, value object thuần Java (không phụ thuộc Google DTO hoặc Spring MVC).
4. **`infrastructure/`**: implementation của provider HTTP, Spring Data persistence, config và mapping.

**Dependency rule:** `api -> application -> domain`. Infrastructure triển khai các port được sở hữu bởi application/domain; domain không gọi infrastructure. Các module khác chỉ dùng public contract, theo ADR-001.

```text
HTTP Request
   -> DiscoveryController (api)
   -> SearchPlacesUseCase (application)
      -> GoogleDiscoveryPort <--- GooglePlacesAdapter (infrastructure)
      -> OwnedPlaceRepository <--- PostGIS adapter (licensed data only)
      -> Owned RankingStrategy (domain, owned/licensed data only)
      -> UserPreferences port <--- PostgreSQL adapter (infrastructure)
   -> SearchResponse DTO
```

Ví dụ hợp đồng outbound port (tên class minh họa, không khóa API thiết kế cuối):

```java
public interface GoogleDiscoveryPort {
    List<GoogleDisplayCandidate> searchNearby(NearbyCriteria criteria);
    List<GoogleDisplayCandidate> searchText(TextCriteria criteria);
}
```

`GoogleDisplayCandidate` là model nội bộ chỉ dùng trong vòng đời request; không trả thẳng `GooglePlacesResponse` từ application/domain. Luồng owned dùng port/model riêng, không chuyển Google candidates sang domain ranking: xem ADR-004/005. Tên class chỉ minh họa, không khóa thiết kế Java cuối cùng.

## 4. Nguyên tắc chi tiết

- Không truyền JPA entity ra REST response; không chuyển cấu trúc Google JSON thành domain object một cách trực tiếp ở controller.
- Không gắn `@Transactional` quanh một use case có HTTP call kéo dài; ưu tiên gọi provider ngoài transaction rồi mở transaction ngắn cho phần ghi DB nếu cần.
- Không tạo `IUserService`, `IAuthService` và mapper chỉ để đủ hình thức; interface có mục đích khi làm port, thay thế implementation hoặc dùng contract liên module.
- Validation hình thức ở DTO, business invariant ở domain/use case.
- Spring Security xử lý xác thực; authorization sở hữu tài nguyên vẫn được kiểm tra trong application layer.
- DTO/contract cần hỗ trợ giá trị thiếu (`rating`, giờ mở cửa, price) và nguồn dữ liệu đi kèm, không tự suy đoán.

## 5. Pattern đi kèm và phân biệt

- **Adapter:** chuyển đổi Google API sang `GoogleDiscoveryPort`, không phải chỉ bọc HTTP request.
- **Repository:** trừu tượng hóa persistence; Spring Data JPA có thể dùng ở infrastructure.
- **Strategy:** đóng gói thuật toán ranking, xem ADR-005.
- **Facade:** có thể đơn giản hóa API một subsystem nhưng không bảo đảm domain độc lập với vendor.
- **Template Method:** tái sử dụng quy trình qua kế thừa; không ưu tiên cho ranking cần chuyển đổi thuật toán linh hoạt.

## 6. Hệ quả

**Tốt:** domain ranking kiểm thử không cần chạy Spring context; provider được mock/stub; đổi HTTP client không ảnh hưởng contract; database thay đổi ít lan truyền.

**Đánh đổi:** thêm mapper, interface ở ranh giới; người mới cần hiểu nguyên tắc dependency; tránh biến package thành nghi lễ nhiều tầng vô ích.

## 7. Kiểm chứng

- Unit test domain ranking chỉ dùng JUnit, không phụ thuộc Google HTTP hay PostgreSQL.
- Contract test của Google adapter với stub server: test timeout, missing fields, API error.
- Test không cho `domain` import package `org.springframework.web`, Google client DTO hoặc JPA entity.
- Integration test controller/service với Testcontainers và fake provider.
- Review kiến trúc đảm bảo controller không truy cập trực tiếp repository hoặc Google client.

## 8. Khi nào xem xét lại

- Nếu toàn bộ module chỉ CRUD rất nhỏ, có thể rút gọn lớp domain độc lập.
- Nếu nhiều use case ngày càng phức tạp, tăng cường domain model và domain-specific ports thay vì tiếp tục nhồi application service.
- Nếu cần thay đổi framework/cách deploy, có thể áp dụng thêm ranh giới Clean/Hexagonal nhưng không đại tu trước khi có động lực.

## 9. Tham khảo

- [Spring Modulith – Verifying Application Module Structure](https://docs.spring.io/spring-modulith/reference/verification.html)

> **Kết luận:** Giữ layered dễ hiểu cho CV, bổ sung port ở nơi thay đổi/phụ thuộc hạ tầng để đạt khả năng kiểm thử và tiến hóa thiết thực.
