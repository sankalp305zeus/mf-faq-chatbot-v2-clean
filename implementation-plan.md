# Implementation Plan — Mutual Fund FAQ Assistant

Derived from: `Milestone RAG.docx` (problem statement + architecture), `.projectgraph/artifacts/ARCHITECTURE.md`, `RESEARCH.md`, `PRD.md`.
Status: **PLANNING ONLY — no code written.** Awaiting design-gate approval.
Mode: ai-rag · LLM: Groq · Embeddings: BGE-small-en-v1.5 · Vector store: ChromaDB.

Rule: do not start a phase until the previous phase's exit criteria are met.

---

## Project structure (target)

```
mf-faq-chatbot/
├── docs/                      # problemStatement.md, architecture.md, edge-case.md, deployment-plan.md
├── data/
│   ├── raw/                   # fetched HTML/markdown per URL (+ timestamp)
│   ├── processed/             # parsed sections & chunks
│   └── index/                 # ChromaDB files
├── ingestion/
│   ├── fetch.py  parse.py  chunk.py  index.py  run.py
├── scheduler/
│   └── daily.py
├── app/
│   ├── main.py  classifier.py  retriever.py  generator.py  validator.py  formatter.py
├── ui/
│   └── index.html
├── config/
│   └── corpus.yaml            # 5 URLs + scheme metadata + aliases
├── tests/
│   ├── test_classifier.py  test_retrieval.py  test_refusal.py
├── .github/workflows/ingest.yml
├── .env.example
└── README.md
```

---

## Phase map

| Phase | Scope | Key files |
|-------|-------|-----------|
| 0 | Foundation / setup | skeleton, deps, `.env.example`, `config/corpus.yaml` |
| 1 | Ingestion: fetch → parse → chunk | `ingestion/fetch.py`, `parse.py`, `chunk.py` |
| 2 | Embedding + index | `ingestion/index.py`, `data/index/` |
| 3 | Retrieval | `app/retriever.py` |
| 4 | Generation + validation (Groq) | `app/generator.py`, `app/validator.py` |
| 5 | API + classifier + compliance | `app/main.py`, `classifier.py`, `formatter.py` |
| 6 | Minimal UI | `ui/index.html` |
| 7 | Scheduler (10:00 AM IST) + deploy | `scheduler/daily.py`, GitHub Actions, `deployment-plan.md` |

**Critical path:** 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7.

---

## Phase 0 — Foundation
**Goal:** Runnable repo skeleton, no business logic.

### Tasks
- [ ] Create package layout, `.gitignore`, pinned `requirements.txt`
- [ ] `.env.example` (GROQ_API_KEY, EMBED_MODEL, CHROMA_DIR, RATE_LIMIT) — no real secrets
- [ ] `config/corpus.yaml`: 5 schemes with slug, scheme_name, category, source_url, aliases
- [ ] `docs/problemStatement.md` + `docs/architecture.md` (port from spec)

### Exit criteria
- Fresh clone → `pip install` → imports succeed
- No secrets in git (only `.env.example`)
- `corpus.yaml` lists exactly the 5 HDFC URLs

### Smoke test
```bash
pip install -r requirements.txt && python -c "import app, ingestion"
```

---

## Phase 1 — Ingestion (fetch → parse → section-extract → chunk)
**Goal:** Turn 5 live Groww pages into clean, section-tagged chunks.

### Tasks
- [ ] `fetch.py` — HTTP GET each corpus URL; save raw HTML/markdown to `data/raw/` with fetch timestamp
- [ ] `parse.py` — strip nav/footers/duplicate chrome; extract scheme-specific content
- [ ] Section extraction into the 9 tags: `overview, expense_ratio, exit_load, minimum_investment, benchmark, tax, fund_management, investment_objective, fund_house`
- [ ] `chunk.py` — **section-aware chunking** (~200–400 tokens), overlap only within same section; keep each fund-manager bio intact in one `fund_management` chunk
- [ ] Attach metadata per chunk: `source_url, scheme_name, section, last_updated`

### Chunking strategy (decided)
Section-aware, not fixed-window. One chunk per coherent section; only split when a section exceeds ~400 tokens, with small intra-section overlap. Fund-management bios are never split. Rationale: queries map 1:1 to sections, so section-scoped chunks maximize retrieval precision and keep citations exact.

### Deliverables
| File | Purpose |
|------|---------|
| `ingestion/fetch.py` | Fetch + timestamp raw pages |
| `ingestion/parse.py` | Clean + section-tag content |
| `ingestion/chunk.py` | Section-aware chunks + metadata |

### Exit criteria
- All 5 URLs fetched to `data/raw/` with timestamps
- Each scheme yields chunks covering available sections; no nav/footer chrome
- Every chunk has all 4 metadata fields

### Smoke test
```bash
python ingestion/fetch.py && python ingestion/parse.py && python ingestion/chunk.py
# inspect data/processed/ for tagged chunks
```

---

## Phase 2 — Embedding + index
**Goal:** Searchable persistent vector store.

### Tasks
- [ ] `index.py` — embed chunks with **BGE-small-en-v1.5** (sentence-transformers)
- [ ] Upsert into **ChromaDB** (persistent, `data/index/`) with metadata
- [ ] Build/refresh scheme metadata index (`last_fetched_at`)
- [ ] `run.py` — atomic ingestion entrypoint chaining fetch→parse→chunk→index

### Decisions (locked)
- **Embeddings: BGE-small-en-v1.5** — free/local; sufficient for short factual chunks (BGE-large is overkill at this scale).
- **Store: ChromaDB** — needs metadata filtering + upsert; FAISS lacks native filters and speed is irrelevant for ~50–150 chunks.

### Exit criteria
- ChromaDB persisted with all chunks + metadata; chunk count logged
- Re-running `run.py` upserts (no duplicates), refreshes `last_fetched_at`

### Smoke test
```bash
python ingestion/run.py   # logs URLs fetched + chunk count
```

---

## Phase 3 — Retrieval
**Goal:** Precise scheme-scoped retrieval.

### Tasks
- [ ] `retriever.py` — **two-stage**: (1) resolve scheme from query via slug/name/alias; (2) semantic top-k (k=3–5) filtered by `source_url`/`scheme_name`, with section boost when intent detected (e.g. "fund manager" → `fund_management`)
- [ ] Return chunks + metadata (for citation + footer)
- [ ] Handle no-scheme-resolved (ask to disambiguate / best-match)

### Retrieval strategy (decided)
Metadata filter first (cheap, exact on tiny corpus), then vector similarity within the scheme subset; boost the section matching detected intent. This beats pure semantic search because the corpus is small and queries are scheme- and section-specific.

### Exit criteria
- Sample queries return the correct scheme's chunks for each of the 9 sections
- Out-of-corpus scheme → no false match

### Smoke test
```bash
python -c "from app.retriever import retrieve; print(retrieve('expense ratio of HDFC Mid Cap'))"
```

---

## Phase 4 — Generation + validation (Groq)
**Goal:** Grounded, compliant answers.

### Tasks
- [ ] `generator.py` — **Groq** call with system prompt: facts-only, no advice, use only provided context, ≤3 sentences, ≤1 URL
- [ ] `validator.py` — post-gen checks: ≤3 sentences (truncate/regen); citation in allowlist (else replace with best retrieved URL); no advisory language (→ refusal); grounding (key facts in chunks); strip performance numbers
- [ ] Deterministic fallback (link-only) when LLM unavailable / `MOCK_LLM=1`

### Exit criteria
- Factual query → ≤3-sentence grounded answer with allowlisted citation + footer
- Validator catches off-allowlist citation, advisory phrasing, ungrounded claims
- Fallback returns valid JSON when Groq is down

### Smoke test
```bash
MOCK_LLM=1 python -c "from app.generator import answer; print(answer('expense ratio HDFC Mid Cap'))"
```

---

## Phase 5 — API + classifier + compliance
**Goal:** Single endpoint enforcing routing + privacy.

### Tasks
- [ ] `classifier.py` — label factual / advisory / comparison / performance / out-of-scope (rules first, LLM fallback for ambiguous)
- [ ] Refusal handler — polite, facts-only, AMFI/SEBI educational link, no retrieval
- [ ] `main.py` — `POST /api/chat` accepting `{ "message": string }`; orchestrate classify → RAG or refusal → format
- [ ] PII guard — reject/strip PAN, Aadhaar, account #, OTP, email, phone before LLM
- [ ] `formatter.py` — enforce response contract + JSON `{answer, citation_url, last_updated, is_refusal}`
- [ ] Basic per-IP rate limiting; structured logging (class, scheme, scores, latency — no PII)
- [ ] `tests/` — classifier, retrieval, refusal

### Exit criteria
- Factual vs advisory/comparison/perf/oos routed correctly per query routing matrix
- PII never reaches LLM, never stored/echoed
- All tests pass

### Smoke test
```bash
uvicorn app.main:app & curl -s localhost:8000/api/chat -d '{"message":"exit load on HDFC Defence Fund"}'
```

---

## Phase 6 — Minimal UI
**Goal:** Clean chat interface (Stitch-styled, Groww-inspired).

### Tasks
- [ ] `ui/index.html` — welcome message + disclaimer "Facts-only. No investment advice."
- [ ] 3 clickable example questions (incl. a fund-management one)
- [ ] Free-text input; render answer + citation link + last-updated footer
- [ ] Never prompt for / accept PII

### Exit criteria
- Disclaimer + 3 examples visible; answers render citation + footer
- Refusals display the educational link

### Smoke test
```bash
# open ui/index.html against running API; click each example
```

---

## Phase 7 — Scheduler + deployment
**Goal:** Daily corpus refresh + live demo.

### Tasks
- [ ] `scheduler/daily.py` — trigger `ingestion/run.py` at **10:00 AM IST (04:30 UTC)** via APScheduler/cron
- [ ] Atomic index swap (chat serves old index during re-index); log start/status/URLs/chunk count; retry once on failure
- [ ] GitHub Actions scheduled workflow (`.github/workflows/ingest.yml`, cron in UTC) for repo-hosted refresh
- [ ] Test scheduler locally, then on GitHub Actions
- [ ] `docs/deployment-plan.md` (Zomato-project style); deploy API + static UI; persistent vector DB volume
- [ ] README: setup, AMC/schemes, RAG architecture, known limitations, disclaimer snippet

### Exit criteria
- Scheduler fires ingestion at 10:00 AM IST locally and via GitHub Actions (verified in logs)
- Deployed demo answers factual queries and refuses advisory ones
- README + deployment-plan complete

### Smoke test
```bash
python scheduler/daily.py --run-now   # verify ingestion triggers + logs
```

---

## Latency targets

| Operation | Target |
|-----------|--------|
| Retrieval (Chroma, filtered) | < 200 ms |
| Groq LLM call | < 4 s |
| End-to-end (p95) | < 5 s |

---

## Edge cases to cover (→ `docs/edge-case.md`)
- Vague scheme ("HDFC fund expense ratio") → disambiguate or best-match
- Multi-scheme in one query → resolve or ask to pick one
- Section missing on a page (e.g. ELSS lock-in N/A) → say data unavailable + link
- Performance/return question → link-only, never compute
- PII in message → strip/reject before LLM
- Groww HTML change / fetch failure → retry once, serve previous index, log
- LLM down / malformed output → deterministic link-only fallback
- Citation not in allowlist → validator replaces with best retrieved URL
- Empty / gibberish query → friendly prompt with the 3 examples

---

## Definition of done
- [ ] Factual queries answered with one allowlisted citation + last-updated footer
- [ ] Advisory / comparison / performance / out-of-scope queries refused with educational link
- [ ] No PII collected, stored, or echoed; stateless API
- [ ] Daily ingestion at 10:00 AM IST (local + GitHub Actions)
- [ ] Deployed demo + README + disclaimer snippet
