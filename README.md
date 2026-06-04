# Mutual Fund FAQ Assistant

A facts-only RAG chatbot that answers verifiable questions about HDFC mutual fund schemes. Every response is grounded in official source data, capped at three sentences, and includes a single citation link. Advisory, comparison, and performance queries are refused by design.

Built as part of the PM Club AI Engineering milestone.

---

## What it does

- Answers factual queries: expense ratio, exit load, minimum SIP, benchmark, riskometer, fund manager details, investment objective
- Refuses non-factual queries: "Should I invest?", "Which fund is better?", return projections
- Cites exactly one source URL per answer with a `Last updated from sources:` footer
- Refreshes its corpus daily at 10:00 AM IST via a scheduler

**Corpus** — 5 HDFC scheme pages on Groww:

| Scheme | URL |
|--------|-----|
| HDFC Mid Cap Fund Direct Growth | groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| HDFC Large Cap Fund Direct Growth | groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| HDFC Small Cap Fund Direct Growth | groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| HDFC Gold ETF Fund of Fund Direct Plan Growth | groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| HDFC Defence Fund Direct Growth | groww.in/mutual-funds/hdfc-defence-fund-direct-growth |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  OFFLINE PIPELINE  (daily, 10:00 AM IST)                    │
│                                                             │
│  Groww URLs ──► fetch.py ──► parse.py ──► chunk.py         │
│                  (raw HTML)  (__NEXT_DATA__  (section-aware  │
│                               structured     chunker)        │
│                               extraction)                    │
│                                    │                         │
│                               index.py                       │
│                         (BGE-small-en-v1.5)                 │
│                                    │                         │
│                              ChromaDB                        │
│                          collection: mf_faq                  │
└────────────────────────────┬────────────────────────────────┘
                             │  51 chunks, 9 sections,
                             │  5 schemes, 384-dim embeddings
┌────────────────────────────▼────────────────────────────────┐
│  ONLINE PATH  (per user request)                            │
│                                                             │
│  User query                                                 │
│      │                                                      │
│      ▼                                                      │
│  Query Classifier ──► Advisory / Comparison / OOS          │
│      │ Factual              │                               │
│      ▼                      ▼                               │
│  Scheme Resolver        Refusal Handler                     │
│  (alias matching)       + AMFI/SEBI link                   │
│      │                                                      │
│      ▼                                                      │
│  Retriever                                                  │
│  1. Filter ChromaDB by slug                                 │
│  2. Semantic top-k (k=3), section-boosted                   │
│      │                                                      │
│      ▼                                                      │
│  Groq LLM  (constrained: facts-only, ≤3 sentences)         │
│      │                                                      │
│      ▼                                                      │
│  Output Validator                                           │
│  (citation allowlist · sentence count · grounding)         │
│      │                                                      │
│      ▼                                                      │
│  Response: { answer, citation_url, last_updated,           │
│              is_refusal }                                   │
│      │                                                      │
│      ▼                                                      │
│  Minimal Chat UI  (disclaimer · 3 examples · no PII)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Ingestion | `requests` + `BeautifulSoup` | Static HTML fetch; KPIs extracted from `__NEXT_DATA__` SSR payload |
| Embeddings | `BGE-small-en-v1.5` (sentence-transformers) | Free, local, 384-dim; sufficient for 51 short factual chunks |
| Vector store | `ChromaDB` (persistent) | Metadata filtering + upsert; FAISS lacks native filters |
| LLM | `Groq` (Llama-3.x) | Fast inference; constrained system prompt + post-gen validator |
| API | `FastAPI` + `uvicorn` | Single `POST /api/chat` + `GET /health` endpoints |
| UI | `Streamlit` (`ui/streamlit_app.py`) | Dark-theme three-column chat interface with history and fund details panel |
| Scheduler | `APScheduler` + GitHub Actions | Daily 10:00 AM IST corpus refresh |
| Language | Python 3.9+ | — |

---

## Setup

```bash
git clone https://github.com/sankalp305zeus/mf-faq-chatbot-v2.git
cd mf-faq-chatbot-v2

# Install dependencies
python3 -m pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — add GROQ_API_KEY (required for generation)
```

### 1. Build the index

```bash
# Full pipeline: fetch → parse → chunk → embed → index (~80s first run; ~19s after BGE is cached)
python3 -m ingestion.run

# Re-index from cached HTML without re-fetching
python3 -m ingestion.run --skip-fetch
```

### 2. Run the API

```bash
uvicorn app.main:app --reload --port 8000
# Health check: curl http://localhost:8000/health
```

### 3. Run the UI

```bash
# In a separate terminal (API must be running)
streamlit run ui/streamlit_app.py
# Opens at http://localhost:8501
```

### 4. Run tests

```bash
python3 -m pytest tests/ -q
# 164 pass, 20 skipped (integration tests that require live Groq)
```

### 5. Run the daily scheduler (optional — for local development)

```bash
python3 -m scheduler.daily
# Triggers ingestion.run at 10:00 AM IST every day
```

---

## Current status

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Repo scaffold, config, deps | ✅ Done |
| 1 | Fetch → parse → section extraction → chunking | ✅ Done |
| 2 | BGE embeddings → ChromaDB index | ✅ Done |
| 3 | Two-stage retriever (scheme filter + semantic) | ✅ Done |
| 4 | Groq generation + output validator | ✅ Done |
| 5 | FastAPI endpoint + query classifier + compliance | ✅ Done |
| 6 | Streamlit chat UI | ✅ Done |
| 7 | Daily scheduler + deployment | ✅ Done |

**164 tests pass** (42 classifier, 43 generation, 68 retrieval, 11 other). 20 skipped (live Groq integration tests).

**What works end-to-end:** factual queries are answered with a grounded ≤3-sentence response and one allowlisted citation. Advisory, comparison, performance, and out-of-scope queries are refused with a static AMFI/SEBI link. PII is rejected before reaching the retrieval or generation layers. The full pipeline — index build, API, and UI — runs locally with a single `GROQ_API_KEY`.

---

## Repository structure

```
mf-faq-chatbot-v2/
├── config/
│   └── corpus.yaml          # 5 corpus URLs + scheme aliases + refusal links
├── data/
│   ├── raw/                 # Fetched HTML + per-scheme metadata (gitignored)
│   ├── processed/           # Section JSON + chunk JSON per scheme (gitignored)
│   └── index/               # ChromaDB files (gitignored)
├── ingestion/
│   ├── config.py            # Shared paths, section tags, corpus loader
│   ├── fetch.py             # HTTP GET corpus URLs → data/raw/
│   ├── parse.py             # __NEXT_DATA__ extraction → structured sections
│   ├── sections.py          # 9 schema-aware section builders + validation
│   ├── chunk.py             # Section-aware chunker → data/processed/
│   ├── index.py             # BGE embed + ChromaDB upsert
│   └── run.py               # Atomic pipeline entrypoint
├── app/
│   ├── main.py              # FastAPI: POST /api/chat, GET /health, PII guard, rate limit
│   ├── classifier.py        # 5-class query classifier (factual/advisory/comparison/perf/oos)
│   ├── retriever.py         # Two-stage ChromaDB retrieval (scheme filter + semantic top-k)
│   ├── generator.py         # Groq generation with constrained system prompt + fallback
│   ├── validator.py         # Post-gen checks: sentence count, citation allowlist, grounding
│   └── formatter.py         # JSON response builder; suppresses footer on empty last_updated
├── scheduler/
│   └── daily.py             # APScheduler: triggers ingestion at 10:00 AM IST
├── ui/
│   └── streamlit_app.py     # Dark-theme chat UI: 3-column layout, history, fund details panel
├── .github/workflows/
│   └── ingest.yml           # GitHub Actions: daily cron at 04:30 UTC (10:00 AM IST)
├── tests/
│   ├── test_sections.py     # 18 structured extractor tests
│   └── test_chunk.py        # 10 chunker tests
├── .projectgraph/           # ProjectGraph OS — project memory + agent handoffs
├── implementation-plan.md   # Full 7-phase plan with exit criteria
├── .env.example
└── requirements.txt
```

---

## Deployment

The application deploys to Railway as two services (API + UI). See [`docs/deployment-plan.md`](docs/deployment-plan.md) for the full step-by-step guide.

**Quick reference:**

| Service | Start command | Key env var |
|---------|--------------|-------------|
| API | `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `GROQ_API_KEY` |
| UI | `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0` | `API_BASE=<api-url>` |

On every deploy, `startCommand` runs ingestion first — building `data/index/` inside the runtime container — then starts uvicorn. This ensures the ChromaDB collection exists in the same filesystem the API reads from. (Railway's `releaseCommand` runs in a separate ephemeral container whose filesystem is discarded before the runtime container starts; see [`docs/deployment-plan.md`](docs/deployment-plan.md) for a full explanation.) Daily re-ingestion is fully automated:

```
GitHub Actions cron (04:30 UTC = 10:00 AM IST)
  → ingestion succeeds → POST RAILWAY_DEPLOY_HOOK_URL
  → Railway startCommand: python -m ingestion.run && uvicorn …
  → fresh index built in runtime container → new deployment goes live
```

Two repository secrets are required: `GROQ_API_KEY` and `RAILWAY_DEPLOY_HOOK_URL` (Railway dashboard → API service → Settings → Deploy Hooks). See [`docs/deployment-plan.md`](docs/deployment-plan.md) for full setup instructions.

---

## ProjectGraph OS

This project uses [ProjectGraph OS v4-beta](https://github.com/sankalp305zeus/ProjectGraph-OS) — a structured AI orchestration system built on local markdown files.

Every phase is driven by a five-agent pipeline (Maya → Nova → Atlas → Forge → Sentinel) with schema-enforced handoffs. Key files:

| File | Purpose |
|------|---------|
| `.projectgraph/CONTEXT.md` | Project identity, mode (`ai-rag`), constraints, rules |
| `.projectgraph/ACTIVE.md` | Current phase, last decision, next action |
| `.projectgraph/SUMMARY.md` | Rolling compressed memory (decisions, risks, what failed) |
| `.projectgraph/artifacts/` | PRD, Architecture, Implementation plan, Eval criteria |
| `.projectgraph/journal/` | Append-only phase handoffs with confidence and escalation |

A Sentinel review after Phase 1 caught that keyword-based HTML extraction was producing label-only content (no values). The parser was rewritten to extract directly from Groww's `__NEXT_DATA__` SSR payload — a structural fix, not a patch.

---

## Disclaimer

**Facts-only. No investment advice.**

This assistant retrieves and presents factual information from public sources. It does not provide investment recommendations, compare fund performance, or offer financial advice. Always consult a SEBI-registered advisor before making investment decisions.

Sources: Groww scheme pages (reference context). Data reflects the last successful ingestion run.
