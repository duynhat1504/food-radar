# ADR-008: Rule-based Recommendation trên dữ liệu có quyền; AI parser sau MVP

- **Trạng thái:** Accepted
- **Người quyết định:** Chủ dự án FoodRadar
- **Ngày chấp thuận:** 2026-11-20
- **Giới hạn:** AI parser thuộc giai đoạn sau MVP và cần ADR/API contract riêng trước khi bật.
- **Ngày:** 2026-11-04
- **Phạm vi:** Recommendation quality, model roadmap, evaluation, privacy
- **Liên quan:** [ADR-004](0004-google-places-provider.md), [ADR-005](0005-recommendation-strategy.md), [ADR-006](0006-sync-and-async-processing.md)

## 1. Bối cảnh

FoodRadar muốn gợi ý quán phù hợp với vị trí, sở thích, ngân sách và tình huống (giờ ăn, đi nhóm). MVP chưa có click history, rating nội bộ, labeled relevance dataset hoặc menu đáng tin cậy để huấn luyện/evaluate ML. Dùng LLM ngay cho mỗi truy vấn làm tăng chi phí/latency và có nguy cơ hallucination.

## 2. Các phương án

| Phương án | Điểm mạnh | Điểm yếu | Đánh giá |
|---|---|---|---|
| **Rule-based + weighted ranking trên owned/licensed data** | Giải thích được, dễ test, không cần training set, rẻ | Cần dữ liệu quán thật hợp lệ để dùng public | **Chọn cho demo MVP và nguồn owned khi sẵn sàng** |
| Content-based filtering | Dùng đặc trưng quán/user để cá nhân hóa | Cần metadata đầy đủ và hợp pháp | Có thể mở rộng |
| Collaborative filtering | Học từ hành vi cộng đồng | Cold-start, sparsity, bias; cần đủ dữ liệu | Chưa phù hợp MVP |
| Hybrid recommendation | Kết hợp nhiều tín hiệu, có tiềm năng cải thiện | Tăng độ phức tạp/đánh giá | Cho đồ án sau |
| LLM trực tiếp đề xuất danh sách quán | Natural language dễ dùng | Có thể bịa quán/giá, latency/cost, khó đo | Không chọn làm nguồn quyết định sự thật |
| NLP/LLM **chỉ parse filter** | UX tự nhiên mà logic tìm/rank vẫn kiểm soát được | Cần validation, schema, fallback | Giai đoạn 2 nếu có nhu cầu |

## 3. Quyết định

MVP có hai luồng với quyền xử lý khác nhau:

1. **`GOOGLE_DISCOVERY`:** dùng Google Nearby/Text để lấy quán thật; giữ nguyên thứ tự provider, không hard filter cục bộ, không trích xuất feature để tính distance/score/reasons và không dùng Google Content làm đầu vào AI. Metadata phải nói rõ giới hạn bán kính và coverage (ADR-004/009).
2. **`OWNED_DATA`:** chỉ với dữ liệu owned/licensed/synthetic có provenance, thực hiện strict radius và hard filters có thể kiểm chứng; trích xuất rating đã điều chỉnh, distance, category/context; dùng trọng số/version và `reasons[]` dựa trên dữ kiện có thật theo ADR-005. Synthetic chỉ cho test/demo offline, không hiển thị như quán thật ở public.
3. **Feedback:** ngoài MVP. Chỉ thiết kế lại khi có consent, retention, quyền xóa và nguồn dữ liệu phù hợp.

Ví dụ giải thích hợp lệ cho **owned/licensed data**: "Cách vị trí bạn chọn 1,2 km; thuộc loại món bạn đã chọn" nếu tọa độ và loại món đều có bằng chứng. Không tạo suy đoán "giá dưới 70.000đ" nếu thiếu menu đáng tin.

### 3.1. AI sau MVP: phân tích ý định tìm kiếm

Tính năng AI đầu tiên được đề xuất là xử lý **câu do người dùng nhập** để trả `SearchCriteria` có cấu trúc, ví dụ món/từ khóa, loại quán và bán kính. Đây là hỗ trợ nhập liệu, **không phải mô hình xếp hạng quán**. Trước khi bật cần ADR/API contract riêng cho schema, chi phí, thời gian phản hồi, xử lý dữ liệu và UX. Backend xác thực output theo schema/allowlist và cho người dùng sửa bộ lọc trước khi tìm. Bộ lọc không được nguồn tìm kiếm hỗ trợ phải hiện lỗi hoặc được người dùng bỏ chọn, không bị bỏ âm thầm. Không gửi GPS chính xác, Google review hoặc Google Place payload vào mô hình; nếu parser lỗi/không chắc, dùng form tìm kiếm thủ công.

Text Search chỉ trả quán liên quan từ khóa; AI không được diễn giải kết quả là bằng chứng quán đang bán một món. Không để LLM tự tạo tên quán, sao, giá, giờ mở cửa hoặc lý do gợi ý.

Google cung cấp `reviewSummary` AI trong Places API (New), nhưng tài liệu khu vực hỗ trợ kiểm tra lại ngày 2026-11-12 chưa liệt kê Việt Nam; không dùng làm phụ thuộc của MVP tại Việt Nam. Nếu hỗ trợ sau này, phải tuân thủ disclosure, attribution và links theo policy nguồn.

### 3.2. Ví dụ response cho owned-data demo

```json
{
  "requestId": "2c17262d-2e59-438a-9435-781c2e70e019",
  "sourceMode": "OWNED_DATA",
  "rankingMode": "RELEVANCE",
  "scoreVersion": "relevance-owned-v1",
  "retrievalMode": "OWNED_POSTGIS",
  "radiusPolicy": "FOODRADAR_ENFORCED",
  "isRadiusStrict": true,
  "isExhaustive": false,
  "candidateCount": 1,
  "coverageNotice": "Chỉ xếp hạng trong tập dữ liệu owned đã lập chỉ mục",
  "results": [
    {
      "provider": "FOODRADAR_OWNED",
      "providerPlaceId": "synthetic-example-id",
      "displayName": "Quán giả lập cho kiểm thử",
      "location": { "latitude": 10.777, "longitude": 106.701 },
      "distanceMeters": 640,
      "ownedRating": 4.6,
      "userRatingCount": 450,
      "foodRadarScore": 0.82,
      "confidence": "HIGH",
      "unknownFields": ["PRICE"],
      "reasons": ["Cách vị trí chọn 640 m", "Thuộc loại món bạn đã chọn"],
      "attributions": []
    }
  ]
}
```

JSON là **dữ liệu giả cho test/demo offline**, không phải kết quả quán thật hoặc lời khẳng định đã tính ra score này. [OpenAPI](../openapi.yaml) là nguồn chuẩn cho payload.

## 4. Lộ trình thuật toán

### Phase MVP

- Google Discovery theo provider order; baseline `DISTANCE`, `RATING`, `RELEVANCE` chỉ chạy trên owned/licensed/synthetic data.
- Từ khóa thường hoạt động không cần AI. AI parser chưa thuộc hợp đồng MVP v1.
- Unit tests/golden tests, normalized score, missing-data policy, score version.
- Theo dõi p95 search latency và tỉ lệ trả danh sách rỗng; không bật analytics hành vi mặc định.

### Phase đồ án tốt nghiệp

- Xây tập relevance judgments/feedback tự nguyện và hợp pháp. Phân biệt dữ liệu do FoodRadar sở hữu với Google Maps Content khi thu thập nhãn.
- Xây baseline Content-based và Hybrid model.
- So sánh với rule-based bằng NDCG@K, Precision@K, Recall@K khi có labels và định nghĩa ground truth hợp lý.
- Báo cáo tính đa dạng, độ mới, độ phủ và cold-start; nêu giới hạn số candidates Google API.
- Thử parser tiếng Việt cho câu người dùng sau khi xác định contract, UX và chi phí; mô hình chỉ nhận câu người dùng, không nhận dữ liệu Google.

### Phase có người dùng

- A/B testing dựa vào metric có ý nghĩa (click-through, save rate, survey) và cỡ mẫu đủ tin cậy; tôn trọng consent/retention.
- Chỉ thử learning-to-rank trên dữ liệu và đặc trưng được quyền dùng. Không dùng Google Maps Content để huấn luyện, kiểm thử, xác thực hoặc tinh chỉnh AI theo điều khoản hiện hành; cần rà soát thêm trước mỗi use case mới.
- Xem xét bias: quán ít review, quán mới, nhóm người dùng khác nhau, business sponsorship phải minh bạch.
- Thiết kế user consent, feedback deletion, chống lạm dụng hành vi giả.

## 5. Hệ quả

**Lợi ích:** dễ ship MVP, chi phí dự đoán tốt, tính giải thích mạnh, test độc lập với provider, có baseline có thể so sánh khi nghiên cứu.

**Đánh đổi:** personalization chưa sâu, trọng số thủ công, dữ liệu nguồn thiếu làm độ chính xác giới hạn; metric business không thể suy ra chỉ từ unit tests.

## 6. Kiểm chứng

- Cùng input/score version/owned dataset => cùng output order; Google giữ provider order.
- Không có item ngoài bộ candidates trả về từ nguồn hợp lệ.
- Filter strict không báo một quán đạt điều kiện nếu field đó unknown.
- 100% `reason` khớp facts đang có trong candidate/context.
- Benchmark scoring trên candidate synthetic tách khỏi chi phí/latency Google API.
- Có baseline và tiêu chí đánh giá trước khi thử AI, tránh 'AI' chỉ là tên gọi marketing.
- Khi triển khai AI parse sau MVP: test schema lỗi, prompt injection, bán kính vượt giới hạn, thiếu trường và fallback khi model timeout; không có Google payload/GPS chính xác trong prompt hoặc log.

## 7. Khi nào xem xét lại

- Có dữ liệu hợp pháp, đủ phong phú để chứng minh ML tốt hơn baseline.
- User cần tìm bằng ngôn ngữ tự nhiên và bộ lọc hiện có không đủ.
- Nhiều dạng context và sở thích khiến rules khó quản lý.
- Business objectives thay đổi, cần học ranking từ phản hồi thực tế.

## 8. Tham khảo

- [Nearby Search (New) – giới hạn candidate/ranking](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
- [Google Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Maps Platform Terms of Service](https://cloud.google.com/maps-platform/terms)
- [AI-powered review summaries – supported regions](https://developers.google.com/maps/documentation/places/web-service/review-summaries)

> **Kết luận:** Đồ án mạnh khi có baseline, dữ liệu, phương pháp và so sánh; việc gắn LLM từ ngày đầu không tự tạo ra giá trị khoa học hoặc kỹ thuật.
