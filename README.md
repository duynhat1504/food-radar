# FoodRadar – Bộ tài liệu thiết kế hiện hành (MVP Backend Java)

**Bản tài liệu:** rà soát 2026-11-12. Bộ tài liệu gồm 9 ADR, SRS v1, OpenAPI v1 và tài liệu thiết kế/kiểm chứng đi kèm.

## Đọc theo thứ tự

1. [SRS v1 – yêu cầu MVP](docs/product-requirements.md)
2. [ADR 001–009 (danh mục)](docs/adr/README.md), đặc biệt [ADR-004](docs/adr/0004-google-places-provider.md), [ADR-005](docs/adr/0005-recommendation-strategy.md), [ADR-009](docs/adr/0009-candidate-retrieval.md)
3. [High-Level Architecture](docs/architecture-overview.md)
4. [OpenAPI v1](docs/openapi.yaml)
5. [Data & Privacy](docs/data-and-privacy.md)
6. [Recommendation Evaluation Plan](docs/recommendation-evaluation.md)
7. [Google Places setup, cost and quotas](docs/google-places-setup-and-cost.md)
8. [Phase 0 validation](docs/phase0-validation.md) và [Remaining release gates](docs/release-readiness.md)

## Trạng thái tài liệu và triển khai

- **Tài liệu thiết kế:** Đã rà soát từng ADR và đồng bộ các điểm về quyền dữ liệu, phạm vi AI, một provider search call và giới hạn bán kính. [Danh mục ADR](docs/adr/README.md) ghi đề xuất xử lý từng quyết định. Cả 9 ADR vẫn `Proposed` vì chưa có phê duyệt chính thức của chủ dự án.
- **Đã kiểm tra offline:** OpenAPI/schema và các quy tắc chính bằng kiểm thử synthetic. Kiểm tra này không thay thế integration test của ứng dụng Spring Boot.
- **Chưa hoàn tất:** Google Places live smoke, cấu hình billing/quota trên Google Cloud, xác nhận licensing/use case, UI attribution, privacy/terms, load test thực tế và production release. Không có key hoặc dữ liệu thực trong gói.
- **Phân tách chính:** `GOOGLE_DISCOVERY` giữ thứ tự từ Google, không tự tính score hoặc hậu lọc khoảng cách. `OWNED_DATA` chạy strict radius và recommendation trên dữ liệu do FoodRadar sở hữu/có giấy phép. AI parser tiếng Việt được đề xuất cho sau MVP, cần ADR/API contract riêng trước khi bật.

## Cách kiểm tra

Tại thư mục `FoodRadar/` sau khi giải nén:

```bash
python -m pip install pyyaml
python -m unittest discover -s tests -p 'validate_contract.py' -v
```

Trên Windows PowerShell, script `scripts/google-places-smoke.ps1` chỉ chạy khi đã có Google Cloud project, key được hạn chế, billing/quota và sự chấp thuận phát sinh phí. Đọc [hướng dẫn](docs/google-places-setup-and-cost.md) trước. Không commit API key.

**Lưu ý:** Bộ hồ sơ đã được sửa để trình chủ dự án quyết định, **không** có nghĩa là mọi kiểm chứng bên ngoài đã hoàn tất hay phần mềm đã được triển khai.
