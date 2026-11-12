# Google Places – Practical setup & cost controls (2026-11-09)

**Purpose:** Tạo điều kiện kiểm chứng live với phí nhỏ, có quota và khả năng audit; không phải cam kết free 100% hoặc thông báo billing đã kích hoạt.

## 1. Account-side checklist (chưa thực hiện)

1. Tạo Google Cloud Project riêng cho FoodRadar PoC; bật billing và Places API (New).
2. Tạo API key restricted tới Places API; cấu hình **application restriction** tương thích nơi chạy script (server public IP nếu áp dụng IP restriction). Tuyệt đối không đưa key vào repo/log/frontend.
3. Giới hạn quota per method ở mức thử nghiệm thấp, ví dụ tối đa vài chục requests/ngày; nếu Google Console không cho mức mong muốn, đặt backend call cap và disable feature flag. Quota không đảm bảo cap tiền tuyệt đối trong mọi tình huống.
4. Tạo Billing budget alert, ví dụ $5 thử nghiệm rồi đánh giá lại; **alert chỉ cảnh báo**.
5. Theo dõi SKU thực trong Billing Reports, không chỉ đo bằng HTTP calls.
6. Đảm bảo logo/attribution, Terms/Privacy và licensing trước khi public UI.

## 2. FieldMask và SKU dự kiến

| Request | Mask | Tier dự kiến |
|---|---|---|
| Nearby | `places.id,places.displayName,places.googleMapsUri,places.attributions` | Nearby Search Pro |
| Text | `places.id,places.displayName,places.googleMapsUri,places.attributions` | Text Search Pro |
| Details | `id,displayName,googleMapsUri,attributions` | Place Details Pro |
| Ratings optional | add `places.rating,places.userRatingCount` to Search | Search Enterprise, feature off by default |

- Enterprise rating fields are **not** a precondition for Google Discovery default; Google results may have no rating in listing.
- OpenNow advanced fields have Enterprise cost; MVP Google mode rejects openNow filter rather than querying then filtering.
- Request-level costs are determined by highest applicable field tier. Verify actual active billing table and regional/contract terms.

## 3. Illustrative unit prices from public global table (subject to change)

| SKU | Monthly free events listed | First paid tier USD/1,000 |
|---|---:|---:|
| Nearby Search Pro | 5,000 | $32 |
| Text Search Pro | 5,000 | $32 |
| Nearby Search Enterprise | 1,000 | $35 |
| Text Search Enterprise | 1,000 | $35 |
| Place Details Pro | 5,000 | $17 |

Example: 8,000 Nearby Pro calls and 3,000 Text Pro calls in one billing period, ignoring other costs, might cost `(8000-5000)*$0.032 = $96` for Nearby and `$0` for Text at these tiers. Verify SKU allocations and total billing with the actual project. Currency conversions/discounts/taxes omitted. Do **not** treat this as an approved budget.

**References:** [Global pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [SKU details](https://developers.google.com/maps/billing-and-pricing/sku-details/places), [Field tier map](https://developers.google.com/maps/documentation/places/web-service/data-fields).
