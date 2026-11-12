# FoodRadar – Recommendation evaluation plan (Proposed v1.1)

- **Cập nhật:** 2026-11-09. Xem [ADR-005](adr/0005-recommendation-strategy.md).
- **Scope:** Owned/licensed/synthetic dataset only. Không dùng Google Maps Content để train/test/validate model.

## 1. Evaluation targets

- Offline determinism: same request + candidate data + version => same order and score.
- Hard filters: radius, min rating/review count, openNow strict; null cannot pass hard filter.
- Ranking robustness: rating sparse review shrinkage; distance monotonic; neutral missing value policy; tie breakers.
- Relevance: chỉ đo Precision@K / Recall@K / NDCG@K khi có independent labeled judgments từ nguồn có quyền sử dụng.
- Business goal later: opt-in anonymous aggregate click/save rates, không tự bật analytics trong MVP.

## 2. Synthetic dataset (dev/test)

Create small known-location fixtures with scores/review counts and explicit licensing label `SYNTHETIC`. Include edge cases at distance 0, radius boundary and beyond, rating null, userRatingCount null, openNow unknown, two exact ties and invalid data. Do not display it as genuine HCMC restaurant content to users.

## 3. Strategy comparisons

| Baseline | Evaluation |
|---|---|
| DISTANCE | ascending distance, deterministic |
| RATING (Bayesian-adjusted) | less sensitive to low review-count; `m`,`C` recorded with version |
| RELEVANCE | 0.4 rating, 0.3 distance, 0.2 category, 0.1 context; ablate and tune with legitimate labels |

`confidence` means feature completeness, NOT P(quán ngon). Score version changes on weights/m/C/missing policies. Report datasets, number of searches, labeling process and coverage limitations in thesis, not fabricated accuracy.

## 4. Release policy

`GOOGLE_DISCOVERY` is evaluated for provider response latency/errors/coverage communication only. Do not use Google data to benchmark or train learned rankers without explicit permission. Public ranking on Google candidate data remains release-gated.
