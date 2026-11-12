# ADR-003: PostgreSQL là database chính; chưa chọn MongoDB làm primary store

- **Trạng thái:** Proposed
- **Rà soát:** 2026-11-12; đề xuất chấp thuận PostgreSQL/Flyway sau khi thu gọn schema MVP
- **Ngày:** 2026-11-04
- **Phạm vi:** Data model, persistence, geospatial roadmap
- **Liên quan:** [ADR-004](0004-google-places-provider.md), [ADR-007](0007-redis-caching.md)

## 1. Bối cảnh

Dữ liệu MVP do FoodRadar quản lý gồm user, refresh session, preferences và favorites. Interaction/feedback, audit nghiệp vụ và menu/restaurant do chủ quán trực tiếp tạo là khả năng sau MVP. Các quan hệ user–favorite–place reference, uniqueness và lịch sử thay đổi cần tính toàn vẹn. Dữ liệu quán đến từ Google Places **không mặc định được lưu lâu dài** theo ADR-004. Địa lý do FoodRadar sở hữu sẽ được bổ sung theo roadmap.

## 2. Các phương án

| Phương án | Điểm mạnh | Hạn chế/đánh đổi | Đánh giá |
|---|---|---|---|
| **PostgreSQL** | ACID, FK/unique, SQL analytics, JSONB, hệ sinh thái PostGIS | Cần migration, schema discipline; horizontal sharding không tự động | **Chọn** |
| MySQL/InnoDB | ACID, SQL/JPA tốt, dễ vận hành | Có hỗ trợ spatial nhưng không chọn hệ sinh thái này cho roadmap PostGIS | Hoàn toàn khả thi cho MVP |
| MongoDB | Document linh hoạt, aggregation, 2dsphere index, transaction | Mô hình many-to-many/constraints phức tạp khác SQL; không có lợi thế rõ cho core domain hiện tại | Không chọn làm primary |
| SQL Server | Relational/transaction/spatial tốt | Hệ sinh thái, bản quyền/triển khai có thể phức tạp hơn mức cần thiết | Không ưu tiên |
| PostgreSQL + MongoDB ngay từ MVP | Mỗi loại cho một workload | Dual DB, consistency và vận hành tăng mạnh | Không chọn |

**Lưu ý:** Không có kết luận PostgreSQL luôn nhanh hơn MySQL hoặc NoSQL không hỗ trợ transaction. Sự phù hợp với mô hình dữ liệu và vận hành là yếu tố chính.

## 3. Quyết định

- Một PostgreSQL là **source of truth** cho dữ liệu nghiệp vụ FoodRadar được quyền lưu.
- Dùng **Spring Data JPA** cho CRUD và Spring transaction; SQL/named query hoặc jOOQ khi đo được truy vấn cần tối ưu. Không lạm dụng ORM với truy vấn địa lý nặng.
- Database schema versioning dùng **Flyway** cho MVP; thay đổi công cụ migration cần quyết định mới.
- Bật constraints ở DB thay vì chỉ kiểm tra tại service.
- **PostGIS là khả năng mở rộng**, chỉ bật khi dự án có kho tọa độ địa điểm hợp pháp tự quản lý. Không coi đó là lý do lưu lại trái phép các Google Places response.

### 3.1. Logical schema khởi đầu (minh họa)

| Bảng | Thuộc quyền | Dữ liệu và ràng buộc |
|---|---|---|
| `users` | identity | `id`, `email` unique, password hash, status, timestamps |
| `user_preferences` | profile | `user_id` FK/unique, budget, configurable preferences |
| `favorite_places` | favorites | `user_id` FK, `provider`, `provider_place_id`, unique kết hợp |
| `refresh_sessions` | identity | chỉ lưu hash token, expiry và trạng thái revoke |

**Sau MVP hoặc khi có dữ liệu hợp lệ:** `interaction_events`, `recommendation_feedback`, `owned_places` cần migration riêng, provenance, consent/retention và quyết định bật tính năng. Không tạo chúng như một phần schema tối thiểu để ngụ ý đã có dữ liệu quán thật.

**Ví dụ constraint chống lưu trùng:**

```sql
CREATE TABLE favorite_places (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL,
    provider_place_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider, provider_place_id)
);
```

Với dữ liệu Google, `provider_place_id` giữ Place ID và **không** thêm các cột sao chép tên, rating, ảnh, tọa độ Google như dữ liệu lâu dài nếu không có quyền tương ứng. Khi hiển thị favorite, cần lấy dữ liệu phù hợp từ nguồn tại thời điểm sử dụng.

### 3.2. PostGIS (giai đoạn có dữ liệu địa điểm tự quản lý)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
-- Khi owned_places có cột location geography(Point,4326):
CREATE INDEX idx_owned_places_location
ON owned_places USING GIST (location);

SELECT id, name
FROM owned_places
WHERE ST_DWithin(
    location,
    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
    :radius_meters
);
```

`ST_MakePoint` nhận longitude trước latitude; `geography` tính khoảng cách bằng mét. Kiểm tra query plan bằng `EXPLAIN (ANALYZE, BUFFERS)` trên bộ dữ liệu được quyền sử dụng.

## 4. Database design policy

1. **Schema thay đổi phải có migration**, không dùng `ddl-auto=update` trên production.
2. Id nội bộ nên là UUID hoặc key được chọn nhất quán; định danh Google lưu độc lập dưới dạng `(provider, provider_place_id)`.
3. FK, unique constraint, CHECK constraint được ưu tiên cho invariant dữ liệu.
4. Index theo workload đã đo: `favorites(user_id, created_at)`, `interaction_events(user_id, occurred_at)` khi cần; tránh tạo index chỉ theo cảm tính.
5. `JSONB` chỉ dùng cho thuộc tính đa dạng ít ràng buộc; dữ liệu lọc/JOIN thường xuyên nên có cột chuẩn hóa.
6. Dùng connection pooling (HikariCP), query timeout, transaction ngắn, backup/restore test.
7. Thiết kế retention/consent/xóa lịch sử tìm kiếm riêng; không lưu GPS chính xác mặc định khi chưa có lý do và thông báo phù hợp.

## 5. Hệ quả

**Ưu điểm:** quan hệ rõ, transaction đáng tin cậy, reporting bằng SQL, PostGIS cho roadmap geospatial, stack Java dễ tuyển dụng.

**Nhược điểm:** schema migration bắt buộc; PostgreSQL đơn lẻ vẫn là một nút cần backup/HA; write scaling và dữ liệu sự kiện lớn sẽ cần cân nhắc partitioning/archival sau này.

## 6. Kiểm chứng

- Integration tests với PostgreSQL Testcontainers kiểm tra unique constraint, FK, rollback và concurrent insert favorite.
- Migration từ DB trống chạy thành công trong CI và deploy.
- Query thường dùng có index hợp lý và `EXPLAIN` được kiểm tra khi có dữ liệu.
- Test backup/restore ở môi trường thử nghiệm trước khi có người dùng thật.
- Không có bảng lưu trái phép raw Google Places payload.

## 7. Khi nào xem xét lại

- Workload dữ liệu hành vi đạt quy mô lớn và có nhu cầu analytics riêng (có thể bổ sung warehouse/columnar store).
- Search full-text/phức hợp tăng cao, cần công cụ tìm kiếm chuyên dụng.
- Workload document độc lập có schema thay đổi mạnh, có giá trị khi dùng NoSQL.
- Dữ liệu địa lý nội bộ trở thành nguồn chính: kích hoạt PostGIS và đánh giá spatial index.

## 8. Tham khảo

- [PostgreSQL – JSON types/JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [PostgreSQL – Index types](https://www.postgresql.org/docs/current/indexes-types.html)
- [PostGIS – ST_DWithin](https://postgis.net/docs/ST_DWithin.html)
- [Google Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies)

> **Kết luận:** SQL là lựa chọn theo bản chất dữ liệu; PostgreSQL thắng MySQL chủ yếu nhờ roadmap PostGIS/JSONB và hệ sinh thái, không vì MySQL không đáp ứng MVP.
