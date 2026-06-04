# Active

Phase: build
Agent: Forge
Mode: ai-rag

## Objective
Phase 3 complete + Sentinel FAR fixes applied. 96 tests pass (68 retrieval, 28 prior). Smoke test 13/13 OK (8 positive + 5 competitor queries). All 9 sections return correct top chunk.

## Last handoff
File: journal/2026-06-04-build-forge-p3-far.md (to be written on next handoff)
Summary: Sentinel review found 9 issues (2 critical, 2 high, 3 medium, 2 low). All critical + high + medium issues addressed. FAR-01: competitor AMC guard added to _scheme_score. FAR-02: false-match test now asserts scheme_resolved=False with 5 competitor parametrize cases. FAR-03: two-pass retrieval guarantees intent section at position 0. FAR-04: "strategy" replaced with "investment strategy"; "exit strategy" added to exit_load keywords. FAR-05: disambiguation hint tests added. FAR-06: supported_schemes field added to RetrievalResult. FAR-07/08/09 deferred as specified.

## Last decision
Two-pass retrieval (FAR-03): pass-1 fetches exact-section chunks via compound ChromaDB where filter; pass-2 fetches semantic top-k; merge deduplicates by id, section chunks at front. Competitor guard (FAR-01): frozenset of 20 AMC tokens; alias/token-overlap paths return 0.0 when query contains a competitor token, so generic aliases never false-fire.

## Blocker
None.

## Next
Phase 4 — implement app/generator.py (Groq, constrained system prompt, ≤3-sentence factual answers) and app/validator.py (post-gen checks: sentence count, citation allowlist, advisory language, grounding). FAR-07 (cold-start warmup) to be resolved in Phase 5 app/main.py startup hook.
