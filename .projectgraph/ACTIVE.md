# Active

Phase: build
Agent: Forge
Mode: ai-rag

## Objective
Phase 4 complete + Sentinel FAR fixes applied. 139 tests pass (43 generation, 68 retrieval, 28 prior). Smoke test 7/7 OK. Full multi-agent workflow: Maya (scope), Atlas (arch), Forge (impl), Sentinel (review + FAR-P4-01/02 fixed).

## Last handoff
File: journal/2026-06-04-build-forge-p4.md
Summary: Implemented app/generator.py (Groq integration, 6-path decision tree, MOCK_LLM stub, link-only fallback) and app/validator.py (sentence truncation, advisory detection, numeric grounding, citation allowlist). tests/test_generation.py (43 unit + integration tests). Sentinel found 2 low-severity issues fixed: dead test guard removed (FAR-P4-01), `retrieve` moved to local import in smoke test (FAR-P4-02). ARCHITECTURE.md data contract updated for empty last_updated on refusals (FAR-P4-03 note).

## Last decision
Grounding check: numeric substring matching (not token-level NLP) — conservative enough for this corpus, avoids hallucinated numbers reaching the user. Advisory detection: 13 regex patterns on lowercased generated text; forces is_refusal=True on match. Citation always sourced from retrieval_result.source_url (metadata), never extracted from generated text. LLM explicitly forbidden from including URLs in output.

## Blocker
None.

## Next
Phase 5 — app/main.py (POST /api/chat), app/classifier.py (factual/advisory/comparison/perf/oos routing), app/formatter.py (JSON contract enforcement), PII guard, rate limiting. FAR-07 (BGE cold-start warmup) resolved in Phase 5 startup hook.
