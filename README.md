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
| API | `FastAPI` | Single `POST /api/chat` endpoint *(Phase 5)* |
| UI | Static HTML/JS | Minimal chat interface *(Phase 6)* |
| Scheduler | `APScheduler` + GitHub Actions | Daily 10:00 AM IST corpus refresh *(Phase 7)* |
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
# Edit .env — add GROQ_API_KEY (required for Phase 4+)

# Run the ingestion pipeline (fetch → parse → chunk → embed → index)
python3 -m ingestion.run

# Or re-index without re-fetching (uses cached HTML)
python3 -m ingestion.run --skip-fetch

# Run tests
python3 -m pytest tests/ -q
```

The pipeline takes ~19s on a warm model cache (~80s on first run while BGE downloads).

---

## Current status

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Repo scaffold, config, deps | ✅ Done |
| 1 | Fetch → parse → section extraction → chunking | ✅ Done |
| 2 | BGE embeddings → ChromaDB index | ✅ Done |
| 3 | Two-stage retriever (scheme filter + semantic) | ⬜ Next |
| 4 | Groq generation + output validator | ⬜ Planned |
| 5 | FastAPI endpoint + query classifier + compliance | ⬜ Planned |
| 6 | Minimal chat UI | ⬜ Planned |
| 7 | Daily scheduler + deployment | ⬜ Planned |

**What works today:** the full offline pipeline. Run `python3 -m ingestion.run` and the vector store is built with 51 chunks across 9 sections for all 5 schemes. Retrieval via ChromaDB is functional; the online API and UI are not yet built.

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
├── app/                     # Online API layer (Phases 3–5, not yet built)
├── scheduler/               # Daily trigger (Phase 7, not yet built)
├── ui/                      # Chat interface (Phase 6, not yet built)
├── tests/
│   ├── test_sections.py     # 18 structured extractor tests
│   └── test_chunk.py        # 10 chunker tests
├── .projectgraph/           # ProjectGraph OS — project memory + agent handoffs
├── implementation-plan.md   # Full 7-phase plan with exit criteria
├── .env.example
└── requirements.txt
```

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
