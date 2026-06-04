# Active

Phase: build
Agent: Forge
Mode: ai-rag

## Objective
Phase 1 fully complete (chunk.py done). Phase 2 complete: 51 chunks embedded with BGE-small-en-v1.5 (384-dim) and persisted to ChromaDB collection 'mf_faq'. Full parse→chunk→embed→index pipeline runs atomically via run.py in ~19s.

## Last handoff
File: journal/2026-06-04-build-forge-p2.md
Summary: Implemented chunk.py (finish P1), index.py (BGE embed + ChromaDB upsert), run.py (atomic pipeline). 28 tests pass. 51 chunks in collection. Retrieval smoke test: slug correct on 5/5, section correct on 3/5 — expected; two-stage filter in Phase 3 will resolve section misses.

## Last decision
ChromaDB 0.5.x uses PersistentClient (not legacy Settings constructor). BGE query prefix used at query time, not embed time. Section metadata filter is confirmed necessary for precision — motivates Phase 3 two-stage retrieval.

## Blocker
None.

## Next
On go-ahead: Phase 3 — implement app/retriever.py with two-stage retrieval (scheme slug filter → semantic top-k within scheme, with section boost when query intent is detectable).
