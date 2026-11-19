# ADR-007: Caching có điều kiện; Redis chỉ cho dữ liệu được quyền cache và workload có lợi ích đo được

- **Trạng thái:** Accepted
- **Người quyết định:** Chủ dự án FoodRadar
- **Ngày chấp thuận:** 2026-11-20
- **Ngày:** 2026-11-04
- **Phạm vi:** Caching, data ownership, quota control, performance
- **Liên quan:** [ADR-003](0003-postgresql-primary-database.md), [ADR-004](0004-google-places-provider.md), [ADR-006](0006-sync-and-async-processing.md)

## 1. Bối cảnh

FoodRadar có nhiều truy vấn lặp lại và external Places API tính phí theo field/SKU. Caching có thể tăng tốc khi dữ liệu hợp lệ được lưu. Nhưng một TTL 5 phút **không tự biến dữ liệu Google Places thành dữ liệu được phép cache**. Dữ liệu GPS và lịch sử tìm kiếm còn liên quan quyền riêng tư. Ở MVP, chưa có bằng chứng Redis giúp đáng kể so với tăng chi phí triển khai.

## 2. Các phương án

| Phương án | Ưu điểm | Nhược điểm | Kết luận |
|---|---|---|---|
| Không cache data ở MVP | Đơn giản, ít stale state, ít sai policy | Có thể tăng query DB/latency | Chấp nhận ban đầu |
| Local in-memory cache | Ít vận hành, rất nhanh | Mỗi replica khác nhau; mất khi restart | Có thể dùng dữ liệu sở hữu ít thay đổi |
| **Redis cache-aside có kiểm soát** | Shared cache nhiều instance, TTL/invalidation/metrics | Vận hành, stale, key security, chi phí | **Dùng khi cần và được phép** |
| Redis lưu nguyên Google Places response | Có vẻ giảm phí nhanh | Rủi ro vi phạm terms/caching restrictions | **Không chọn mặc định** |

## 3. Quyết định

**Không triển khai Redis trong MVP.** Thiết kế **cache eligibility policy theo nguồn dữ liệu** để đánh giá sau này; chỉ đưa Redis vào khi có một use case cụ thể đủ lợi ích đo được và được quyền cache. Khi áp dụng, ưu tiên **cache-aside** với TTL và invalidation rõ ràng. Redis không phải source of truth. Việc kích hoạt Redis cần quyết định triển khai riêng với số liệu trước/sau.

| Nhóm dữ liệu | Chính sách đề xuất |
|---|---|
| Google Place ID | Có thể lưu lâu dài theo ngoại lệ do Google công bố; định danh vẫn có thể thay đổi và cần refresh |
| Google Places name/rating/location/reviews/photos | **Không cache/lưu mặc định**; ngoại lệ chỉ theo điều khoản hiện hành và phạm vi pháp lý được xác minh |
| User preferences do FoodRadar quản lý | Có thể cache per-user, invalidation khi update, hạn chế sensitive data |
| Owned restaurant/menu | Có thể cache sau khi kiểm tra tính cập nhật và quy trình chủ quán sửa |
| Ranking configuration/feature flags tự quản lý | Có thể cache/versioning |
| Derived results dựa vào Google Content | **Không tự động cho là cache được**; phải rà soát điều khoản trước khi lưu |
| User authentication | Không lưu token/PII tùy tiện; chỉ giữ những trạng thái cần thiết theo thiết kế bảo mật |

### 3.1. Quy trình cache-aside (cho dữ liệu FoodRadar sở hữu)

```text
Read -> Redis hit -> return
     -> Redis miss -> PostgreSQL -> optional Redis SETEX -> return
Write -> PostgreSQL commit -> invalidate/update cache
```

- Key namespace: `foodradar:profile:v1:{userId}:preferences` hoặc `foodradar:owned-place:v1:{placeId}`.
- Chọn TTL theo business freshness, **không theo suy đoán về quyền lưu trữ Google**.
- Khi user sửa preferences, phải invalidate key sau commit; xử lý race giữa write/invalidation.
- Không dùng cache key chứa GPS chính xác, email, access token hoặc dữ liệu nhạy cảm ở dạng plaintext.
- Vẫn phải bảo đảm authorization trước khi trả private cache; tránh leak data qua key không gắn user.

## 4. Caching và tối ưu Places API là hai vấn đề khác nhau

Để giảm số API call **mà không lưu trái phép provider content**:

1. UI debounce hành động tìm kiếm; chỉ gọi khi filter thực sự được xác nhận.
2. Rate limit theo user/IP có kiểm soát; chống bot và spam.
3. Field mask tối thiểu, chỉ lấy field phục vụ màn hình; điểm FoodRadar không tính từ Google Content trong MVP.
4. Giới hạn concurrent outbound call; request deduplication cùng thời điểm cần được rà soát về điều khoản và implement không lưu nội dung quá vòng đời request.
5. Cân nhắc quota/budget alerts và fallback sang **nguồn nội bộ được sở hữu**, không giả kết quả.

Redis cũng có thể hỗ trợ distributed rate limiting khi chạy nhiều application replica, nhưng phải kiểm tra tính atomic của thao tác/token bucket và xử lý lúc Redis không khả dụng.

## 5. Hệ quả

**Lợi ích:** tăng tốc phần dữ liệu do FoodRadar sở hữu, có thể scale nhiều node, giảm một số truy vấn PostgreSQL.

**Đánh đổi:** cache invalidation, stale data, thêm thành phần deploy; nếu cache không đúng loại dữ liệu có thể vi phạm chính sách của provider.

## 6. Kiểm chứng

Các kiểm thử Redis dưới đây chỉ áp dụng **khi quyết định bổ sung Redis được chấp thuận**; không phải tiêu chí bắt buộc cho MVP hiện tại.

- Có bảng phân loại dữ liệu `owner/source`, caching policy, TTL, privacy classification.
- Integration test cho cache hit/miss, update/invalidation, Redis outage và multi-user data isolation.
- Monitoring: hit ratio, evictions, memory, timeout, DB query load và latency.
- Load test so sánh có/không Redis chỉ trên **dữ liệu được phép cache**, chứng minh cải thiện trước khi đưa vào production.
- Không có raw Google Places payload/rating/ảnh trong Redis keys/values khi chưa xác minh license exception.

## 7. Khi nào xem xét lại

- Đã đo được load DB, p95 latency hoặc read amplification khiến cache có ích.
- Redis tăng chi phí vận hành vượt giá trị có được.
- Tính cập nhật của owned menu/places yêu cầu invalidation phức tạp hơn.
- Google thay đổi điều khoản lưu trữ/caching hoặc có thỏa thuận license riêng.

## 8. Tham khảo

- [Google Places API policies – caching exceptions](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Places API – Place IDs](https://developers.google.com/maps/documentation/places/web-service/place-id)
- [Google Places API – Usage & Billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)

> **Kết luận:** Cache theo **quyền sở hữu dữ liệu và bằng chứng hiệu năng**, không dùng Redis như 'cách lách' phí API.
