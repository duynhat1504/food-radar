# ADR-005: Strategy Pattern cho Recommendation Engine, chỉ chạy trên nguồn dữ liệu đủ quyền

- **Trạng thái:** Proposed; baseline offline đã được ghi nhận, chưa production ranking
- **Rà soát:** 2026-11-12; đề xuất chấp thuận baseline cho dữ liệu owned/licensed, chưa bật public nếu thiếu dữ liệu thật
- **Ngày gốc:** 2026-11-04
- **Phạm vi:** Scoring, search modes, explainability, provenance
- **Liên quan:** [ADR-004](0004-google-places-provider.md), [ADR-008](0008-rule-based-before-ai.md), [ADR-009](0009-candidate-retrieval.md)

## Vấn đề

MVP muốn sắp xếp theo rating, khoảng cách và độ phù hợp. Các cách này khác nhau và cần test/so sánh. Tuy nhiên, không được mặc định lấy rating/toạ độ Google làm đầu vào để tạo `foodRadarScore` hoặc tính đặc trưng mới: xem ADR-004. Điều này dẫn đến **ranking strategy có quyền chạy theo source**.

## Lựa chọn và lý do

| Lựa chọn | Ưu | Nhược | Kết luận |
|---|---|---|---|
| 1 comparator / switch | Gọn khi một mode | Phình to khi có nhiều thuật toán | Thích hợp cho 1 mode |
| **Strategy Pattern** | Algorithm độc lập, unit test/diff rõ | Nhiều class và selector | Chọn cho OWNED_DATA khi có ≥2 modes |
| Template Method | Chia sẻ flow | Phụ thuộc inheritance, không hợp khi cách scoring khác | Không chọn |
| Chain of Responsibility | Composable filter pipeline | Không thay thế riêng scoring | Có thể dùng cho filter |

## Quyết định kiến trúc

```text
SearchUseCase
  -> SourcePolicy / SearchModePolicy
      GOOGLE_DISCOVERY -> preserve provider order; score=null; no derived distance
      OWNED_DATA       -> hard filters -> RankingStrategy -> explainable scores
```

`RankingStrategy` không nhận Google DTO; chỉ nhận `OwnedPlaceCandidate` với nguồn và quyền sử dụng được xác minh. `GOOGLE_DISCOVERY` trả `rankingMode=PROVIDER_ORDER`; không phải một Strategy được dùng để tự sắp kết quả Google.

Nếu chưa có dataset quán thật đủ quyền, `OWNED_DATA` chỉ chạy trong dev/test hoặc môi trường demo ghi rõ synthetic; public không đưa quán giả vào kết quả và không quảng bá đây là recommendation cá nhân hóa trên quán thật.

```java
public interface RankingStrategy {
    List<RankedPlace> rank(List<OwnedPlaceCandidate> candidates, SearchContext context);
}
```

Các strategy của owned data: `DistanceRankingStrategy`, `AdjustedRatingRankingStrategy`, `WeightedRelevanceStrategy`. `ProviderOrder` là chế độ hiển thị của Google, không được gọi là `RELEVANCE` của FoodRadar.

## Quy tắc lọc ở OWNED_DATA

- Bán kính 100–10.000m dùng PostGIS ST_DWithin/geography hoặc geodesic được kiểm thử; `distanceMeters` là đường chim bay.
- `minRating`, `minUserRatingCount`, `openNow=true` là hard filters: thiếu dữ liệu cần để kiểm chứng => loại; không tự nới ngưỡng.
- `query` với owned data chỉ tìm bằng tên/loại/menu **có quyền lưu**; không suy diễn chắc chắn có món chỉ từ keyword match.
- Giá cụ thể và budget **ngoài MVP**, dù schema có thể mở rộng sau.

## Baseline RELEVANCE (owned/synthetic)

\[
R_{adjusted}=\frac{v}{v+m}R+\frac{m}{v+m}C
\]

Đề xuất thử nghiệm `m=20`, `C=4.0` **trên bộ dữ liệu synthetic** (không lấy trung bình Google). Giá trị `R_adjusted` nằm trong 0–5 nếu R/C nằm trong 0–5.

\[
S = 0.40 \times RatingScore + 0.30 \times DistanceScore
  + 0.20 \times CategoryScore + 0.10 \times ContextScore
\]

Trong đó `RatingScore=R_adjusted/5`, `DistanceScore=max(0,1-distance/radius)`, `CategoryScore`/`ContextScore` nhận 0/0.5/1 theo dữ liệu owned đã xác minh. Missing rating => 0.5 **trung tính trong soft scoring** nhưng không vượt qua hard filter; confidence giảm. Không dùng Google content làm tập kiểm thử/đánh giá ML.

- `RELEVANCE`: `scoreVersion=relevance-owned-v1`, score trong [0,1].
- `DISTANCE`: xếp khoảng cách tăng; `scoreVersion=distance-owned-v1`, score **null** để tránh hiểu là thang chất lượng tổng thể.
- `RATING`: dùng Bayesian-adjusted rating, xếp missing cuối; `scoreVersion=adjusted-rating-owned-v1`, score **null**; UI ghi "rating có điều chỉnh từ dữ liệu FoodRadar", không phải Google.
- Tie-breaker: score (nếu RELEVANCE) giảm, review count giảm khi có dữ liệu, distance tăng, `(provider, providerPlaceId)` lexical để deterministic.

## Transparency & missing signals

`confidence` = độ đầy đủ **tín hiệu scoring**, không phải xác suất quán ngon. Có thể giữ baseline HIGH >=100 lượt review và không thiếu tín hiệu; MEDIUM >=20 và thiếu <=1; còn lại LOW. Đây chỉ là giả định kiểm thử, không phải claim chất lượng. `reasons[]` chỉ mô tả dữ kiện có bằng chứng. `unknownFields[]` ghi rating, price, opening, category, context thiếu.

`GOOGLE_DISCOVERY`: **không** xuất `foodRadarScore`, `scoreVersion`, `confidence`, `reasons[]` do FoodRadar tính; rating nếu trả là thuộc tính hiển thị Google và bắt buộc attribution/chi phí phù hợp. Không gọi kết quả là Top-rated trong cả vùng, ngay cả khi user chỉ thấy 20 kết quả.

## Kiểm thử và tiêu chí chấp nhận

1. Synthetic tests: monotonic distance, Bayesian m/C, missing data, empty, stable tie, 3 strategies, score 0..1.
2. Contract tests: Google mode không gọi Strategy, không reorder Google results, response không có derived score/distance; owned mode không lấy Google DTO.
3. Golden dataset có quyền sử dụng cho Precision@K/NDCG@K khi có labels; không công bố hiệu quả khi thiếu labels.
4. Khi mở thêm ranking dựa trên Google (nếu có giấy phép bằng văn bản), cần ADR follow-up, version mới, privacy/compliance tests và measure bill.

Chấp thuận ADR là chấp thuận thuật toán baseline và ranh giới dữ liệu, không phải xác nhận chất lượng gợi ý. Chỉ công bố hiệu quả khi có nhãn độc lập, metric và dữ liệu hợp lệ theo [kế hoạch đánh giá](../recommendation-evaluation.md).

## Hệ quả và điều kiện xét lại

**Ưu:** có thể code/test ranking cho CV ngay với synthetic/owned data mà không khóa tiến độ bởi Google. **Đánh đổi:** Google Discovery public hiện **không có** custom ranking theo rating; để phục vụ lời hứa sản phẩm đầy đủ cần nguồn dữ liệu hợp lệ hoặc quyền bổ sung. Xem xét lại khi có licensed dataset hoặc quyền sử dụng cụ thể.

## Nguồn

- [Google Maps Terms](https://cloud.google.com/maps-platform/terms)
- [Places Policies](https://developers.google.com/maps/documentation/places/web-service/policies)
