# Summary

Last generated: 2026-06-04 (updated after parser fix — build phase)

## Key decisions
- Mode = ai-rag; compliance-first, accuracy over intelligence
- Corpus = 5 HDFC Groww scheme pages (mid/large/small cap, gold FoF, defence)
- Embeddings = BGE-small-en-v1.5 (free, local); ChromaDB (local, persistent, metadata filtering)
- Retrieval = two-stage: scheme resolve → semantic top-k, section-boosted
- LLM = Groq; constrained system prompt + post-gen output validator
- Daily ingestion at 10:00 AM IST (APScheduler + GitHub Actions)
- Parser extracts mfServerSideData from __NEXT_DATA__ SSR payload directly (not HTML text, not generic JSON walk). Schema-aware builders per section. MissingRequiredField raised if any required key absent.
- Chunking: one chunk per section per scheme; fund_management = one chunk per manager bio. No overlap at this scale.

## Architecture state
Offline pipeline (fetch → parse → chunk → embed → ChromaDB) feeds online path (classify → resolve scheme → retrieve → constrained Groq generation → validate → format). Nine section tags, each with a dedicated structured builder pulling exact fields from mfServerSideData. All 5 schemes parse to 9/9 sections of complete answerable sentences. **Built through Phase 4 + Sentinel FAR fixes:** 51 chunks indexed in ChromaDB. Retrieval layer: two-stage with competitor guard, two-pass section-guarantee query. Generation layer (app/generator.py + app/validator.py): Groq (llama-3.3-70b-versatile, temp=0, max_tokens=256) with constrained system prompt; 6-path decision tree (unresolved refusal, MOCK_LLM stub, Groq success, Groq failure, advisory refusal, grounding fallback); validator enforces ≤3 sentences, advisory language detection (13 patterns), numeric grounding, citation allowlist. GenerationResult dataclass = {answer, citation_url, last_updated, is_refusal, refusal_reason, validation_issues}. 139 tests passing. Remaining: Phases 5–7.

## Known risks
- mfServerSideData key path is Groww-internal and undocumented; key renames silently produce MissingRequiredField errors (detected, not silent)
- One AMC description string truncated mid-word in Groww's payload (source data quality, not parser bug)
- docs/ still empty (Phase 0 deliverable outstanding)
- BGE model cold-start (~5–10 s) violates p95 < 5 s NFR on first request; warmup deferred to Phase 5 app/main.py startup hook (FAR-07)
- Corpus is 5 Groww URLs vs 15–25 specified in Milestone RAG.docx; KIM/SID/AMFI/SEBI pages not yet ingested (FAR-08, Phase 8 backlog)
- Scheme-level last_fetched_at metadata index not written by ingestion/index.py; chunk last_updated used as proxy (FAR-09, Phase 7)

## What didn't work
- Substring keyword matching (v1): "ter" fired on "filter/later". Fixed by word-boundary regex.
- Word-boundary keyword matching (v2): extracted HTML labels not values. Root cause: Groww is Next.js; KPI values are in __NEXT_DATA__, not rendered HTML. Fixed by structured extraction.
- Generic __NEXT_DATA__ JSON flattening: produced "expense_ratio: 0.73" strings but underscore key didn't match "expense ratio" phrase in section keywords. All three approaches abandoned in favour of schema-aware builders.
