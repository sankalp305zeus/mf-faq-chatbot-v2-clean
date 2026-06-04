# Architecture

Owner: Atlas (design) · Date: 2026-06-04 · Source: PRD.md + RESEARCH.md + Milestone RAG.docx

## Goals

| Goal | Rationale |
|------|-----------|
| Facts-only, retrieval-grounded answers | LLM constrained by system prompt + post-gen validator → low hallucination |
| Exactly one allowlisted citation per answer | Verifiability and compliance |
| Compliance gating before retrieval | Advisory/comparison queries refused, never answered |
| Structured-first, LLM-second | Narrow 5-URL corpus + section metadata reduce error and token cost |
| Stateless, no PII | Privacy requirement; no identity-linked storage |
| Graceful degradation | LLM failure → deterministic link-only response, never a crash |

---

## System layers

```
Layer 5 — Presentation   ui/            (chat + disclaimer + examples)
Layer 4 — Application     app/           (API, classifier, orchestrator, formatter)
Layer 3 — Generation      app/generator, app/validator
Layer 2 — Retrieval       app/retriever  + data/index (ChromaDB) + metadata index
Layer 1 — Offline ingest  ingestion/ + scheduler/   (fetch→parse→chunk→embed→index)
```

| Layer | Module | Responsibility |
|-------|--------|----------------|
| 5 | `ui/streamlit_app.py` | Dark-theme Streamlit chat UI; disclaimer chip, 3 example buttons, chat history, fund details panel, citation+footer rendering, no PII prompts |
| 4 | `app/main.py` | `POST /api/chat`; orchestrate classify → route → respond |
| 4 | `app/classifier.py` | Label query: factual / advisory / comparison / performance / out-of-scope |
| 4 | `app/retriever.py` | Two-stage retrieval over ChromaDB |
| 4 | `app/formatter.py` | Enforce ≤3 sentences, 1 citation, footer; build JSON |
| 3 | `app/generator.py` | Constrained Groq generation from retrieved chunks |
| 3 | `app/validator.py` | Post-gen checks: sentence count, citation allowlist, grounding, no advisory/perf |
| 2 | `data/index/` | ChromaDB persistent store (chunks + metadata) |
| 2 | `config/corpus.yaml` | 5 URLs + scheme metadata (slug, name, category, aliases) |
| 1 | `ingestion/fetch.py` | HTTP GET each URL → `data/raw/` with fetch timestamp |
| 1 | `ingestion/parse.py` | Strip chrome; extract scheme content |
| 1 | `ingestion/chunk.py` | Section-aware chunking |
| 1 | `ingestion/index.py` | Embed (BGE) + upsert Chroma + refresh metadata |
| 1 | `ingestion/run.py` | Atomic ingestion entrypoint |
| 1 | `scheduler/daily.py` | APScheduler: trigger run.py at 10:00 AM IST (in-process) |
| 1 | `.github/workflows/ingest.yml` | GitHub Actions cron: trigger run.py at 04:30 UTC = 10:00 AM IST |

---

## Data contracts

### Chat request
```json
{ "message": "string — user question, no session identity" }
```

### Chat response
```json
{
  "answer": "string — ≤3 sentences",
  "citation_url": "string — allowlisted corpus URL (or AMFI/SEBI for refusal)",
  "last_updated": "string — YYYY-MM-DD from chunk metadata; empty string for refusals (no chunks → no date)",
  "is_refusal": "bool"
}
```
Note: `last_updated` is empty for unresolved-scheme and advisory refusals. Phase 5 formatter must suppress the "Last updated" footer when `last_updated` is empty.

### Chunk record (ChromaDB document)
```json
{
  "id": "string — <slug>#<section>#<n>",
  "text": "string — passage for grounding",
  "metadata": {
    "source_url": "string — citation link",
    "scheme_name": "string",
    "section": "string — one of 9 section tags",
    "last_updated": "string — YYYY-MM-DD fetch/parse date"
  }
}
```

### Scheme metadata entry (`config/corpus.yaml` / metadata index)
```json
{ "slug": "string", "scheme_name": "string", "category": "string",
  "source_url": "string", "aliases": ["string"], "last_fetched_at": "YYYY-MM-DD" }
```

---

## Key flows

Online (request):
```
User → POST /api/chat → classify
  ├─ advisory/comparison/perf/oos → refusal handler → AMFI/SEBI link → format → JSON
  └─ factual → resolve scheme → retrieve top-k chunks → Groq (constrained)
            → validator → formatter → JSON (answer + citation + footer)
```

Offline (index, daily 10:00 IST):
```
scheduler → run.py → fetch 5 URLs → parse → section-extract → chunk
         → BGE embed → upsert ChromaDB → refresh metadata (atomic swap)
```

---

## Section tags (chunking + section-boosted retrieval)

`overview · expense_ratio · exit_load · minimum_investment · benchmark · tax · fund_management · investment_objective · fund_house`

---

## Technology choices

| Concern | Choice | Why / Alternatives |
|---------|--------|--------------------|
| Backend | Python + FastAPI | Strong RAG ecosystem; single `/api/chat` |
| Embeddings | BGE-small-en-v1.5 (local) | Free vs paid OpenAI; sufficient for short chunks |
| Vector store | ChromaDB (persistent) | Metadata filtering + upsert; FAISS lacks native filters |
| Retrieval | Two-stage: scheme resolve → semantic top-k (k=3–5), section boost | Precision on tiny corpus |
| LLM | Groq (Llama-3.x) | Fast, cheap; fallback to link-only |
| Ingestion | requests/BeautifulSoup (Playwright if JS-rendered) | Parse Groww pages |
| Scheduler | APScheduler/cron (local) + GitHub Actions (repo) | 10:00 AM IST daily |
| Classifier | Rules first, LLM fallback for ambiguous | Simplicity + accuracy |
| UI | Streamlit (`ui/streamlit_app.py`) | Dark-theme three-column layout; chat history; fund details panel |
| Config | Env vars + `config/corpus.yaml` | No secrets in repo |

---

## Cross-cutting concerns

### Security / Privacy
- API keys (Groq) in env only; never logged or committed
- PII detector strips/rejects PAN, Aadhaar, account #, OTP, email, phone before LLM
- Citation allowlist enforced by validator
- Stateless API; basic per-IP rate limiting

### Reliability
- LLM timeout/failure → deterministic link-only fallback
- Atomic index swap: chat serves old index until new one fully written
- Ingestion retries once on failure, logs error

### Observability
- Structured log per request: query class, scheme resolved, retrieval scores, refusal flag, latency_ms (no PII)
- Ingestion log: start time, status, URLs fetched, chunk count

---

## Known limitations
- Corpus = 5 HDFC Groww pages only; no AMFI/SEBI/KIM/SID ingestion this phase
- Answers reflect last successful daily ingestion (not intra-day)
- Groww is reference context, not HDFC primary documents
- No performance/return analytics by design
- Vague queries ("HDFC fund expense ratio") may need disambiguation or best-match
- Fund-management data limited to what each Groww page exposes
