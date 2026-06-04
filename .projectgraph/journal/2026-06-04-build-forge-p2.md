# Handoff

Phase: build
Agent: Forge
Date: 2026-06-04
Confidence: high

## Objective
Complete Phase 1 (chunk.py) and implement Phase 2 (BGE embed + ChromaDB index + atomic run.py pipeline).

## Completed
- ingestion/chunk.py: section-aware chunker. One merged chunk per section per scheme; one chunk per manager bio for fund_management (bios intact). Writes per-scheme *.chunks.json to data/processed/.
- ingestion/index.py: loads all chunks, embeds with BGE-small-en-v1.5 (sentence-transformers), upserts into ChromaDB PersistentClient collection 'mf_faq' (cosine space, 384-dim). Idempotent upsert — safe to re-run daily.
- ingestion/run.py: atomic entrypoint chaining fetch→parse→chunk→index. Supports --skip-fetch for re-index without re-fetch. Logs timestamps and elapsed time.
- tests/test_chunk.py: 10 unit tests (all pass). Total test suite: 28/28.
- requirements.txt: Phase 2 deps activated (sentence-transformers==3.0.1, chromadb==0.5.5).
- Retrieval smoke test: slug correct 5/5; section correct 3/5 (expected — two-stage filter in Phase 3 resolves the 2 misses).

## Decisions
- ChromaDB 0.5.x: uses PersistentClient, not legacy Settings constructor. Auto-persists on every write; no explicit flush needed.
- BGE query prefix ("Represent this sentence for searching relevant passages: ") applied at query time, not at embed time. Document embeddings are plain text (standard BGE usage).
- Telemetry errors in ChromaDB output are a ChromaDB internal bug (capture() signature mismatch); do not affect functionality. Suppressed in user-facing output.
- Chunk count: 51 total (8 sections × 5 schemes × 1 chunk + 11 fund_management bios).

## Risks
- Section-only retrieval (no scheme filter) returns wrong section for expense_ratio and fund_management queries — two-stage retrieval in Phase 3 is required and confirmed necessary.
- BGE model download (~90MB) on first run adds latency; cached after first execution.
- ChromaDB telemetry errors are cosmetic but noisy — worth suppressing in prod logging.

## Artifacts updated
- ingestion/chunk.py (new)
- ingestion/index.py (new)
- ingestion/run.py (new)
- tests/test_chunk.py (new)
- requirements.txt (Phase 2 deps activated)
- data/processed/*.chunks.json (5 files)
- data/index/ (ChromaDB collection 'mf_faq', 51 docs)
- .projectgraph/ACTIVE.md
- .projectgraph/SUMMARY.md
- .projectgraph/artifacts/IMPLEMENTATION.md

## Next
Agent: Forge
Action: Implement app/retriever.py — two-stage retrieval: (1) resolve scheme slug from query via corpus.yaml aliases, (2) query ChromaDB with slug metadata filter + semantic top-k (k=3), with optional section boost when query intent is detectable (e.g. "expense ratio" → filter section=expense_ratio).
Gate: none
Escalate to: none
Status: ready
