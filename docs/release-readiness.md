# Phase 0 – Issue disposition and next decisions

**Phê duyệt ADR:** 2026-11-20. Chủ dự án đã chấp thuận ADR-001..009 theo [danh mục ADR](adr/README.md). Các cổng triển khai/phát hành dưới đây độc lập với trạng thái ADR và vẫn cần hoàn tất.

| Prior issue | Applied change | Outcome |
|---|---|---|
| P0-01 Google scoring rights | Google Discovery no derived scoring/geo filtering; separate Owned ranking | **Design mitigated; legal/provider approval still OPEN** |
| P0-02 Budget/quota | 1 search call cap; FieldMask profiles; quota/budget playbook | **Design mitigated; account-side setup OPEN** |
| P0-03 Attribution | UI requirements in SRS/ADR + list/map policy | **Requirement documented; UI implementation OPEN** |
| P0-04 Live API | Bounded PowerShell script, no credentials distributed | **Script ready; live execution OPEN** |
| P0-05 Auth/Profile missing | 4 auth ops, user GET/DELETE, preferences GET/PUT in OpenAPI | **Contract draft DONE, tests/implementation OPEN** |
| P1-01 query+placeType | Google 422; owned accepted with legitimate data | **Contract draft DONE** |
| P1-02 minRating=4.3 rounding | Google 422; owned exact hard filter | **No inadvertent Google roundup** |
| P1-03 openNow Google vs Nearby | Google 422; owned strict if field present | **Contract draft DONE** |
| P1-04 Raw Google vs adjusted | Google provider order; owned adjusted RATING labelled | **Contract draft DONE** |
| P1-05 score nullability | Google null, owned mode-dependent | **Contract draft DONE** |
| P1-06 429 conflated | Local 429, provider quota 503 | **Contract draft DONE** |
| P1-07 address manual | GPS or manual map pin only; string geocode deferred | **Scoped explicitly** |
| P1-10 feedback premature | Removed feedback endpoint from MVP v1 (post-MVP) | **Contract draft DONE** |
| P1-11 Load targets | p95/50 RPS targets with provider stub, not claimed achieved | **Tests NOT YET RUN** |
| P1-12 ADR-008 example used Google score | Replaced with owned/synthetic response, separated Google and owned flows | **Document correction DONE; implementation OPEN** |
| P1-13 One-call budget vs 5xx retries | Removed automatic provider search retry from ADR-004/006, SRS and architecture | **Contract decision drafted; implementation OPEN** |
| P1-14 AI MVP scope | NLP parser placed after MVP, with separate ADR/API contract before enablement | **Scope ACCEPTED; implementation remains post-MVP** |
| P1-15 Product promise vs public dataset | Explicit gate for legitimate real-place data before custom public recommendation | **Dataset and quality evidence OPEN** |

## ADR acceptance recorded (2026-11-20)

- ADR-001/002/003/006/007: accepted. ADR-007 means **no Redis in MVP**.
- ADR-004: accepted as a gated integration design; it is not legal clearance.
- ADR-005: accepted as an owned-data ranking baseline without Google-derived processing.
- ADR-009: accepted with Text Search treated as radius **bias only**.
- ADR-008: accepted with separate Google/owned flows and AI parser **after MVP**.

**Open external gates:** Google live API evidence, billing quota configuration, provider/legal licensing, UI branding/attribution, Terms/Privacy, actual test/benchmark results, licensed real-place dataset and evaluation for public custom recommendations.
