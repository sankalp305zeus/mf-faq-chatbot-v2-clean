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
Offline pipeline (fetch → parse → chunk → embed → ChromaDB) feeds online path (classify → resolve scheme → retrieve → constrained Groq generation → validate → format). Nine section tags, each with a dedicated structured builder pulling exact fields from mfServerSideData. All 5 schemes parse to 9/9 sections of complete answerable sentences. **Built through Phase 6 + Sentinel review (no FARs):** 51 chunks indexed in ChromaDB. API layer (app/main.py): FastAPI, POST /api/chat, lifespan BGE warmup (FAR-07 resolved), PII guard (PAN/Aadhaar/mobile/email), slowapi per-IP rate limit (20/minute), structured logging (no PII). Classifier (app/classifier.py): 5-class rules-based (factual/advisory/comparison/performance/out_of_scope), comparison checked before advisory. Formatter (app/formatter.py): footer suppression when last_updated empty. UI (ui/streamlit_app.py): Streamlit, disclaimer banner, 3 example buttons, answer/refusal/citation rendering, API_BASE env var. groq pinned to >=0.13.0 (httpx 0.28.x compatibility). 164 tests passing (20 skipped = integration). Remaining: Phase 7 (scheduler + deployment).

## Known risks
- mfServerSideData key path is Groww-internal and undocumented; key renames silently produce MissingRequiredField errors (detected, not silent)
- One AMC description string truncated mid-word in Groww's payload (source data quality, not parser bug)
- docs/ still empty (Phase 0 deliverable outstanding)
- BGE model cold-start resolved via warmup() in app/main.py lifespan startup (FAR-07 closed)
- Corpus is 5 Groww URLs vs 15–25 specified in Milestone RAG.docx; KIM/SID/AMFI/SEBI pages not yet ingested (FAR-08, Phase 8 backlog)
- Scheme-level last_fetched_at metadata index not written by ingestion/index.py; chunk last_updated used as proxy (FAR-09, Phase 7)

## What didn't work
- Substring keyword matching (v1): "ter" fired on "filter/later". Fixed by word-boundary regex.
- Word-boundary keyword matching (v2): extracted HTML labels not values. Root cause: Groww is Next.js; KPI values are in __NEXT_DATA__, not rendered HTML. Fixed by structured extraction.
- Generic __NEXT_DATA__ JSON flattening: produced "expense_ratio: 0.73" strings but underscore key didn't match "expense ratio" phrase in section keywords. All three approaches abandoned in favour of schema-aware builders.
