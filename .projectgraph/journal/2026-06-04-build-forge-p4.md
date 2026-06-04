# Handoff

Phase: build
Agent: Forge (multi-agent: Maya → Atlas → Forge → Sentinel)
Date: 2026-06-04
Confidence: high

## Objective
Phase 4 — build the generation layer: Groq integration, output validation, refusal handling.

## Agent workflow
- **Maya (scope):** Confirmed Phase 4 boundary = generator.py + validator.py only. Refusal handling at Phase 4 covers unresolved scheme (from retriever), post-gen advisory detection, and LLM fallback. Pre-retrieval classifier (advisory/comparison/OOS) remains Phase 5.
- **Atlas (architecture):** Confirmed GenerationResult data contract matches Phase 5 formatter input. Citation always from `retrieval_result.source_url` (metadata), never extracted from LLM output. Grounding failure → link-only fallback (not regenerate) for Phase 4.
- **Forge (implementation):** Built all files. See below.
- **Sentinel (review):** Found 3 issues — FAR-P4-01 (dead test guard), FAR-P4-02 (module-level retrieve import), FAR-P4-03 (undocumented empty last_updated). FAR-P4-01/02 fixed by Forge. FAR-P4-03 documented in ARCHITECTURE.md.

## Completed

### app/generator.py
- `GenerationResult` dataclass: `{answer, citation_url, last_updated, is_refusal, refusal_reason, validation_issues}`
- `SYSTEM_PROMPT`: 6-rule constrained prompt; explicitly forbids URLs in answer output
- `generate(query, retrieval_result) -> GenerationResult`: 6-path decision tree
  - Path 1: `scheme_resolved=False` → `_unresolved_refusal()` (lists all 5 supported schemes)
  - Path 2: `MOCK_LLM=True` → `_mock_answer()` (top chunk text, validated)
  - Path 3: Groq call → validated answer
  - Path 4: Groq failure → `_link_only_fallback()`
  - Path 5: validator flags advisory language → `_advisory_refusal()`
  - Path 6: validator flags grounding failure → `_link_only_fallback()`
- `_call_groq()`: lazy `from groq import Groq` so ingestion scripts work without groq installed; `temperature=0`, `max_tokens=256`
- Groq key validated via `settings.require_groq()` (raises if empty; never called by ingestion)

### app/validator.py
- `ValidationResult` dataclass: `{answer, citation_url, is_refusal, issues}`
- `split_sentences()`: regex `(?<=[.!?])\s+(?=[A-Z\"])` — handles MF domain well
- `truncate_to_n_sentences(text, n=3)`: silent repair
- `check_advisory(text)`: 13 regex patterns on lowercased text
- `check_grounding(answer, chunks)`: extracts numeric tokens (`\b\d+(?:[.,]\d+)*\s*(?:%|₹|crore|...)?`); checks each against all chunk texts; returns ungrounded numbers
- `check_citation(url)`: allowlist = 5 corpus URLs + AMFI + SEBI refusal links
- `validate(answer, citation_url, retrieval_result) -> ValidationResult`: applies all 4 checks in order

### tests/test_generation.py
- 43 tests total (37 unit, 6 integration with MOCK_LLM, 3 integration with live Groq)
- Coverage: sentence split/truncate, advisory detection (7 positive + 5 negative), grounding (5 cases), citation check, validate() (5 scenarios), generate() (6 unit paths), full pipeline integration (5 queries + unresolved)

## Decisions
- `temperature=0`: deterministic generation essential for a compliance-first system
- `max_tokens=256`: generous for 3 sentences; prevents runaway responses
- Grounding check: numeric substring matching (not NLP) — sufficient for 51 short factual chunks; avoids hallucinated numbers
- Advisory detection: post-generation only in Phase 4; pre-retrieval classification deferred to Phase 5 classifier
- `last_updated=""` for refusals: no chunks → no date; Phase 5 formatter must suppress footer when empty (documented in ARCHITECTURE.md)

## Test results
- Full suite: 139/139 pass (3 skipped = live Groq, correct)
- Smoke test: 7/7 OK (MOCK_LLM mode)

## Artifacts updated
- `.projectgraph/ACTIVE.md`
- `.projectgraph/SUMMARY.md`
- `.projectgraph/artifacts/IMPLEMENTATION.md`
- `.projectgraph/artifacts/ARCHITECTURE.md` (data contract note for empty last_updated)

## Sentinel FAR log
| FAR | Severity | Status | Fix |
|-----|----------|--------|-----|
| FAR-P4-01 | Low | Fixed | Removed dead `not pytest.importorskip` guard in test |
| FAR-P4-02 | Low | Fixed | `retrieve` moved to local import inside `_run_smoke()` |
| FAR-P4-03 | Low | Documented | Empty `last_updated` on refusals noted in ARCHITECTURE.md data contract |

## Next
Agent: Forge
Action: Phase 5 — `app/main.py` (FastAPI POST /api/chat), `app/classifier.py` (factual/advisory/comparison/perf/oos routing, rules-first), `app/formatter.py` (JSON contract enforcement, disclaimer), PII guard, rate limiting, structured logging
Gate: human-approval-required
