# MF FAQ Assistant — Project Handoff

**Date:** 2026-06-07
**Status:** MVP — production verified
**Handoff type:** Self-handoff / future session context

---

## Project Overview

Facts-only chatbot answering mutual fund scheme questions with Groww source citations. Covers 5 HDFC schemes. Refuses advisory, comparison, and performance queries by design. Built for retail investors who need quick factual lookups without navigating dense AMC pages.

**Live URL:** https://groww-chat-buddy.lovable.app
**Backend:** https://mf-faq-chatbot-v2-clean-production.up.railway.app

---

## Architecture

```
User (Lovable frontend)
    │  POST /api/chat
    │  { message, scheme_name }
    ▼
FastAPI — app/main.py
    │  1. PII guard
    │  2. Classify (factual / advisory / comparison / performance / oos)
    │  3. Non-factual → immediate refusal
    │  4. Enrich query: "{message} for {scheme_name}"
    │
    ├─► Retriever — app/retriever.py
    │     Stage 1: resolve_scheme() — alias/token matching
    │     Stage 2: BGE-small-en-v1.5 → ChromaDB semantic search
    │     Two-pass: guaranteed section chunk + semantic top-k
    │
    ├─► Generator — app/generator.py
    │     Groq API — llama-3.3-70b-versatile
    │     Temperature 0, max 256 tokens
    │     System prompt: facts-only, no advice, no URLs
    │
    ├─► Validator — app/validator.py
    │     Sentence truncation (≤3)
    │     Advisory language check
    │     Numeric grounding check (Cr→crore normalised)
    │     Citation allowlist check
    │
    └─► Response: { answer, citation_url, last_updated, is_refusal, scheme_name, section_intent }
```

---

## Deployment Details

| Component | Platform | Config |
|---|---|---|
| Backend API | Railway — `welcoming-expression` project | Auto-deploy from `main` branch |
| GitHub repo | `sankalp305zeus/mf-faq-chatbot-v2-clean` | `main` branch |
| Frontend | Lovable → `groww-chat-buddy.lovable.app` | Connected to Railway backend via `VITE_API_BASE` |
| Ingestion | GitHub Actions — `.github/workflows/ingest.yml` | Daily 10:00 AM IST (04:30 UTC) |

---

## Environment Variables (Railway)

| Variable | Required | Value / Notes |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq console — llama-3.3-70b-versatile |
| `CHROMA_PATH` | Yes | `data/index` |
| `COLLECTION_NAME` | Yes | `mf_faq` |
| `EMBEDDING_MODEL` | Yes | `BAAI/bge-small-en-v1.5` |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` |
| `RATE_LIMIT` | No | `100/minute` (set for friend testing) |
| `ALLOWED_ORIGINS` | No | `*` (wildcard — lock for production) |
| `LOG_LEVEL` | No | `INFO` |
| `MOCK_LLM` | No | `0` |

---

## Corpus

- **5 schemes:** HDFC Mid-Cap, Large Cap, Small Cap, Gold ETF FoF, Defence
- **51 chunks** — 9-11 per scheme, 9 sections each
- **Sections:** overview, expense_ratio, exit_load, minimum_investment, benchmark, tax, fund_management, investment_objective, fund_house
- **Source:** Groww scheme pages — fetched fresh on every Railway deploy + daily GitHub Actions
- **Embeddings:** BGE-small-en-v1.5, dim=384, stored in ChromaDB persistent collection `mf_faq`

---

## Open Issues

| Issue | Severity | Notes |
|---|---|---|
| `RAILWAY_DEPLOY_HOOK_URL` not confirmed in GitHub Secrets | Medium | Daily ingestion runs but Railway may not auto-redeploy with fresh data |
| Proxy IP rate limiting | Low | `RATE_LIMIT` is per-IP; Railway proxy may share IP across users |
| AUM data staleness | Low | AUM changes daily; ingestion refreshes it but Railway redeploy timing matters |
| Pydantic extra field silencing | Low | `ChatRequest` should use `model_config = ConfigDict(extra='forbid')` in v2 |

---

## Future Roadmap

### Near term
1. **Confirm `RAILWAY_DEPLOY_HOOK_URL`** in GitHub Secrets so daily ingestion auto-deploys
2. **Add 14 more schemes** — expand beyond 5 HDFC to other AMCs
3. **Build evaluation dataset** — 24 questions scored for precision and groundedness (BRIEF.md success metric)

### Medium term
4. **Multi-AMC support** — SBI, Axis, Nippon (requires corpus expansion + alias update)
5. **Conversational context** — retain last scheme across turns so users don't need to re-select
6. **Streaming responses** — reduce perceived latency on Groq calls

### Architecture improvements
7. **Integration tests** — pytest suite testing full request payloads end-to-end
8. **Corpus normalisation pass** — standardise unit abbreviations (`Cr` → `crore`) at ingestion so validator doesn't need to compensate
9. **N8N automation** — see PROJECT-HANDOFF.md section below

---

## N8N Integration Opportunities

N8N can automate the operational loop that currently requires manual steps:

| Workflow | Trigger | Action |
|---|---|---|
| **Daily data refresh** | Schedule 10 AM IST | Trigger GitHub Actions ingest → wait for success → POST to Railway deploy hook → Slack/WhatsApp notify |
| **Error alerting** | Railway log webhook | Parse for `grounding_failure` or `Groq failed` → notify via Slack |
| **User feedback capture** | Lovable feedback button → N8N webhook | Log to Notion/Airtable for eval dataset building |
| **Eval dataset builder** | Manual trigger | Pull last N queries from Railway logs → format as JSONL eval pairs → push to GitHub |
| **Uptime monitoring** | Cron every 15 min | Hit `/health` → if non-200, alert via WhatsApp |

N8N replaces manual monitoring, removes the GitHub Actions → Railway → verify → notify manual chain, and gives a no-code dashboard for non-technical stakeholders to see system health.
