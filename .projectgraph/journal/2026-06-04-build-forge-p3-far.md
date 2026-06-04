# Handoff

Phase: build
Agent: Forge (Sentinel FAR execution)
Date: 2026-06-04
Confidence: high

## Objective
Execute all Forge Action Requests raised by Sentinel review of Phase 3.

## Sentinel findings (9 total)

| FAR | Severity | Disposition |
|-----|----------|-------------|
| FAR-01 | Critical | Fixed — competitor AMC guard added to `_scheme_score()` |
| FAR-02 | Critical | Fixed — false-match test now asserts `scheme_resolved is False`; 5 competitor parametrize cases |
| FAR-03 | High | Fixed — section boost replaced with two-pass retrieval (guaranteed-section pass + semantic top-k) |
| FAR-04 | High | Fixed — bare `"strategy"` → `"investment strategy"`; `"exit strategy"` added to exit_load keywords |
| FAR-05 | Medium | Fixed — disambiguation hint tested (near-tie + unambiguous cases) |
| FAR-06 | Medium | Fixed — `supported_schemes: list[str]` added to `RetrievalResult`; populated on `scheme_resolved=False` |
| FAR-07 | Medium | Deferred to Phase 5 `app/main.py` startup hook |
| FAR-08 | Low | Logged — corpus scope gap vs Milestone RAG.docx; Phase 8 backlog |
| FAR-09 | Low | Logged — `last_fetched_at` metadata index deferred to Phase 7 |

## Completed
- `app/retriever.py`: `_COMPETITOR_TOKENS` frozenset (20 tokens); `_query_names_competitor()`; `_scheme_score()` returns 0.0 on alias/token match when competitor present; two-pass `_retrieve_with_section_guarantee()` replaces `_apply_section_boost()`; `supported_schemes` in `RetrievalResult`
- `tests/test_retrieval.py`: 27 new tests (competitor detection, competitor resolution, disambiguation hint, supported_schemes, investment_objective integration, 5-case false-match integration)
- `tests/conftest.py`: created (shared `--run-integration` flag)

## Test results
- Full suite: 96/96 pass
- Smoke test: 13/13 (8 positive + 5 competitor rejections)
- investment_objective top chunk now correct (score 0.69)

## Artifacts updated
- `.projectgraph/ACTIVE.md`
- `.projectgraph/SUMMARY.md`
- `.projectgraph/artifacts/IMPLEMENTATION.md`

## Next
Agent: Forge
Action: Phase 4 — implement app/generator.py + app/validator.py
Gate: human-approval-required (Phase 4 approved in same session)
