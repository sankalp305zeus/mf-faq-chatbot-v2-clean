# Implementation Plan (artifact)

<!-- Owner: Forge (build). Phase map mirrors root implementation-plan.md. -->
<!-- Status: P0 DONE · P1 PARTIAL (fetch+parse+sections done; chunk.py pending). -->

## Progress (2026-06-04)
- **Phase 0 — DONE.** Scaffold, `.gitignore`, `requirements.txt`, `.env.example`, `config/corpus.yaml`. Imports succeed; no secrets committed.
- **Phase 1 — DONE.** `fetch.py` ✅ `parse.py` ✅ `sections.py` ✅ `chunk.py` ✅. 5/5 pages → 51 total chunks (1 per section per scheme; 1 per manager bio for fund_management). 28 tests pass.
- **Phase 2 — DONE.** `index.py` ✅ `run.py` ✅. BGE-small-en-v1.5 (384-dim, cosine), ChromaDB `PersistentClient`, collection `mf_faq`, 51 docs persisted. Atomic pipeline via `run.py --skip-fetch` runs in ~19s.

## Phase map

| Phase | Scope | Layer / area | Key files |
|-------|-------|--------------|-----------|
| 0 ✅ | Setup | Repo + config | skeleton, `.env.example`, `config/corpus.yaml`, deps |
| 1 ✅ | Ingestion | Offline (L1) | `fetch.py`, `parse.py`, `sections.py`, `chunk.py` |
| 2 ✅ | Embed + index | Retrieval (L2) | `ingestion/index.py`, `ingestion/run.py`, `data/index/` |
| 3 | Retrieval | Retrieval (L2) | `app/retriever.py` |
| 4 | Generation | Generation (L3) | `app/generator.py` (Groq), `app/validator.py` |
| 5 | API + compliance | Application (L4) | `app/main.py`, `classifier.py`, `formatter.py` |
| 6 | UI | Presentation (L5) | `ui/index.html` |
| 7 | Scheduler + deploy | Ops | `scheduler/daily.py`, GitHub Actions, `deployment-plan.md` |

**Critical path:** 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7.

## Exit-criteria summary (binary)
- P0: fresh clone installs; imports succeed; no secrets in git
- P1: 5 URLs fetched to `data/raw/`; parsed into 9 section tags; section-aware chunks produced
- P2: chunks embedded (BGE-small) and persisted to ChromaDB with full metadata
- P3: two-stage retrieval returns correct scheme's top-k for sample queries
- P4: Groq returns ≤3-sentence grounded answer; validator catches off-allowlist citation + advisory language; fallback works
- P5: `/api/chat` routes factual vs refusal correctly; PII stripped; rate limit active
- P6: UI shows disclaimer + 3 examples; renders citation + footer; no PII prompts
- P7: scheduler runs ingestion at 10:00 AM IST locally + via GitHub Actions; deployed demo live

## Definition of done
- [ ] Factual queries answered with one allowlisted citation + footer *(P5)*
- [ ] Advisory/comparison/perf/out-of-scope queries refused correctly *(P5)*
- [ ] Daily ingestion at 10:00 AM IST keeps index fresh *(P7)*
- [ ] Deployed demo + README + disclaimer snippet *(P7)*

> Full per-phase tasks, deliverables, smoke tests, and edge cases live in
> `implementation-plan.md` at the repo root.
