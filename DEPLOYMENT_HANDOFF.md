# Deployment Handoff — MF FAQ Chatbot v2

**Created:** 2026-06-05  
**Status:** Production incident in progress — 403 on API calls from Streamlit frontend  
**Freeze reason:** Checkpoint before continued debugging

---

## Project Overview

### Purpose
Facts-only RAG chatbot answering verifiable questions about 5 HDFC mutual fund schemes. Every answer is ≤3 sentences, grounded in a Groww source page, with one citation. Advisory, comparison, and performance queries are refused by design.

### Architecture
```
Offline pipeline (daily):
  GitHub Actions cron (04:30 UTC)
    → python -m ingestion.run (fetch → parse → chunk → BGE embed → ChromaDB)
    → POST RAILWAY_DEPLOY_HOOK_URL → Railway deployment triggered

Online path (per request):
  Browser → Streamlit server (Python)
    → requests.post(API_BASE/api/chat)
    → FastAPI: classify → retrieve → Groq generate → validate → format
    → JSON response → Streamlit renders answer + citation + footer
```

### Tech Stack

| Layer | Choice |
|-------|--------|
| Ingestion | `requests` + `BeautifulSoup`, `__NEXT_DATA__` SSR extraction |
| Embeddings | `BGE-small-en-v1.5` (sentence-transformers, local, 384-dim) |
| Vector store | `ChromaDB` (persistent, `data/index/`) |
| LLM | `Groq` (Llama-3.3-70b-versatile) |
| API | `FastAPI` + `uvicorn`, `POST /api/chat`, `GET /health` |
| UI | `Streamlit` (`ui/streamlit_app.py`) |
| Scheduler | `APScheduler` (`scheduler/daily.py`) + GitHub Actions (`ingest.yml`) |
| Deployment | Railway (two services: API + UI) |
| Language | Python 3.9+ |

---

## Railway Services

### Frontend (Streamlit UI)

| Property | Value |
|----------|-------|
| Service name | `adventurous-inspiration` |
| Public URL | `https://adventurous-inspiration-production-7f7f.up.railway.app` |
| Current start command | `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0` |
| Bound port | 8080 (confirmed in deploy logs) |
| Health check | `/health` — PASSES (confirmed in build logs, deployment ac118735) |
| Status | Online |
| Active deployment | ac118735 (Jun 5, 2026, 04:00 AM GMT+5:30) |

### Backend (FastAPI API)

| Property | Value |
|----------|-------|
| Service name | `mf-faq-chatbot-v2-clean` |
| Public URL | `https://mf-faq-chatbot-v2-clean-production.up.railway.app` |
| Private network URL | `http://mf-faq-chatbot-v2-clean.railway.internal:8080` |
| Expected start command | `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Actual running process | **UNKNOWN** — deploy logs not inspected for this service |
| Status | Online (visible green dot in Railway canvas) |
| Active deployment | **UNKNOWN** |

---

## Deployment Timeline

### Phase: Local success (pre-Railway)
- All 164 tests passing locally
- Full pipeline working: ingestion → retrieval → generation → Streamlit UI
- `python -m ingestion.run && uvicorn app.main:app` → Streamlit calls localhost:8000 → answers correct

### Phase: Initial Railway deployment
- Deployment commit: `c40504c` (Phase 7: scheduler, deployment automation and documentation)
- `railway.toml` created with:
  - `releaseCommand = "python -m ingestion.run"`
  - `startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"`
- Two Railway services created from same repo
- **Incident:** `ValueError: Collection mf_faq does not exist` on first chat request
- `/health` returned 200; `/docs` loaded; `POST /api/chat` reached retriever.py and failed

### Phase: ChromaDB bootstrap fix
- **Root cause identified:** Railway's `releaseCommand` runs in an ephemeral container separate from the runtime container. Filesystem writes (including `data/index/`) are discarded when the release container exits. The runtime container starts from the built image with empty `data/index/`.
- **Fix (commit `9c7d967`):** Removed `releaseCommand`. Changed `startCommand` to `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `railway.toml` comment updated; `docs/deployment-plan.md` and `README.md` updated

### Phase: Streamlit UI deployment
- **User action:** `startCommand` in `railway.toml` changed (commit `21a68ba`) to:
  `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
- **Critical discrepancy introduced:** `railway.toml` comment still says "runs ingestion before uvicorn" but `startCommand` now runs Streamlit. Both Railway services deploy from the same `railway.toml`. If no per-service override exists in Railway dashboard, **both services are now running Streamlit**.

### Phase: 403 incident (current)
- User sets `API_BASE=http://mf-faq-chatbot-v2-clean.railway.internal:8080` on `adventurous-inspiration` service
- Error observed: `Unexpected error: 403 Client Error: Forbidden for url: http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat`
- 403 is returned from Railway private network, not the public internet

### Phase: CORS hardening (commit `72ad5e1`, current HEAD)
- `app/main.py` updated: `allow_origins` now reads from `ALLOWED_ORIGINS` env var (defaults to `"*"`)
- `allow_methods` now includes `OPTIONS`
- **This does not fix the 403** — documented in commit message
- Pushed to `origin/main` — awaiting Railway redeploy

---

## Current Variables

### Frontend service (`adventurous-inspiration`) — from Railway Variables screenshot

| Variable | Value | Status |
|----------|-------|--------|
| `API_BASE` | `http://mf-faq-chatbot-v2-clean.railway.internal:8080` | **Verified** (visible in screenshot) |
| `CHROMA_PATH` | masked | Unverified |
| `COLLECTION_NAME` | masked | Unverified |
| `EMBEDDING_MODEL` | masked | Unverified |
| `FETCH_RETRIES` | masked | Unverified |
| `FETCH_TIMEOUT` | masked | Unverified |
| `FETCH_USER_AGENT` | masked | Unverified |
| `GROQ_API_KEY` | masked | Unverified |
| `GROQ_MODEL` | masked | Unverified |
| Total visible | 12 Service Variables | — |

### Backend service (`mf-faq-chatbot-v2-clean`) — not inspected

| Variable | Value | Status |
|----------|-------|--------|
| All variables | **Not inspected** | **Unverified** |

---

## Known Working Components

- `GET /health` on `adventurous-inspiration` returns 200 (Railway health check passed, deployment ac118735)
- Streamlit UI loads in browser at `adventurous-inspiration-production-7f7f.up.railway.app`
- Streamlit starts and binds to port 8080 (deploy logs confirm)
- `API_BASE` env var is correctly set on the Streamlit service to `http://mf-faq-chatbot-v2-clean.railway.internal:8080`
- URL construction in code: `API_URL = f"{API_BASE}/api/chat"` — correctly appends `/api/chat` (no double slash)
- Full local pipeline: 164/164 tests pass
- `mf-faq-chatbot-v2-clean` service status shows Online (green dot in Railway canvas)
- Port 8080 on `mf-faq-chatbot-v2-clean.railway.internal` **accepts connections** (a 403 is a valid HTTP response, not a TCP failure)

---

## Known Broken Components

- `POST /api/chat` from Streamlit UI returns `403 Client Error: Forbidden for url: http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat`
- End-to-end chat flow is non-functional in production

---

## Current User-Facing Error

Exact error displayed in the Streamlit chat bubble:

```
Unexpected error: 403 Client Error: Forbidden for url: http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat
```

This is surfaced by the `except Exception as exc` handler in `ui/streamlit_app.py:335`:
```python
return {
    "answer": f"Unexpected error: {exc}",
    ...
    "is_refusal": True,
}
```

---

## Investigation Ledger

### FACTS

| ID | Description | Evidence |
|----|-------------|----------|
| F1 | Streamlit service is running Streamlit, not uvicorn | Deploy logs: "You can now view your Streamlit app in your browser. URL: http://0.0.0.0:8080" |
| F2 | Streamlit service bound to port 8080 | Deploy logs, deployment ac118735 |
| F3 | Streamlit service health check at `/health` passes | Build logs: "[1/1] Healthcheck succeeded!" |
| F4 | `API_BASE=http://mf-faq-chatbot-v2-clean.railway.internal:8080` on Streamlit service | Railway Variables screenshot |
| F5 | Full URL called at runtime: `http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat` | Error message in UI screenshot |
| F6 | 403 is returned from Railway private network, not public internet | F5 — URL is `.railway.internal` |
| F7 | `railway.toml` `startCommand` = `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0` | `railway.toml` in repo (current HEAD) |
| F8 | `railway.toml` comment says "runs ingestion before uvicorn" — contradicts actual `startCommand` | `railway.toml` |
| F9 | Application code has no 403-returning path | `app/main.py` — all paths return 200, 422, or 429 |
| F10 | Port 8080 on `mf-faq-chatbot-v2-clean.railway.internal` accepts connections | 403 is a valid HTTP response; TCP connection was established |

### DISPROVEN

| ID | Hypothesis | Why Disproven |
|----|-----------|---------------|
| D1 | 403 from Cloudflare/Railway public edge proxy blocking python-requests | F6: 403 comes from `.railway.internal` — Cloudflare is not in this path |
| D2 | `API_BASE` not set on Streamlit service | F4: visible in Variables screenshot |
| D3 | Wrong URL construction in code | F5: error shows correct constructed URL |
| D4 | Nothing listening on port 8080 at `mf-faq-chatbot-v2-clean.railway.internal` | F10: HTTP 403 received (connection established) |

### UNKNOWNS

| ID | Unknown |
|----|---------|
| U1 | What process is `mf-faq-chatbot-v2-clean` actually running? (Streamlit or uvicorn?) |
| U2 | Does `mf-faq-chatbot-v2-clean` have a custom start command override in Railway dashboard? |
| U3 | What do `mf-faq-chatbot-v2-clean` deploy logs show on startup? |
| U4 | What does `GET http://mf-faq-chatbot-v2-clean.railway.internal:8080/health` return? |
| U5 | What variables are set on the `mf-faq-chatbot-v2-clean` service? |

---

## Railway Evidence

### Screenshot findings

| Screenshot | Finding |
|-----------|---------|
| `adventurous-inspiration` deployment 9eb048a5 details | Start command was `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT` — this was an **older** deployment, not current |
| `adventurous-inspiration` deployment ac118735 build logs | Image push 3.1 GB; health check at `/health` with 5m0s retry window; `[1/1] Healthcheck succeeded!` |
| `adventurous-inspiration` deployment ac118735 deploy logs | `Starting Container` → Streamlit messages → `URL: http://0.0.0.0:8080` |
| `adventurous-inspiration` Variables | 12 variables; `API_BASE=http://mf-faq-chatbot-v2-clean.railway.internal:8080` visible |
| UI at `adventurous-inspiration-production-7f7f.up.railway.app` | Error bubble: `Unexpected error: 403 Client Error: Forbidden for url: http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat` |

### Relevant URLs

| Name | URL |
|------|-----|
| Frontend (Streamlit) | https://adventurous-inspiration-production-7f7f.up.railway.app |
| Backend (API) public | https://mf-faq-chatbot-v2-clean-production.up.railway.app |
| Backend (API) private | http://mf-faq-chatbot-v2-clean.railway.internal:8080 |
| GitHub repo | https://github.com/sankalp305zeus/mf-faq-chatbot-v2-clean |
| Railway project | railway.com/project/a0039133-d59d-4e63-b7af-a527288f5cc2 |

---

## Relevant Files

| File | Relevance |
|------|-----------|
| `railway.toml` | **Critical** — `startCommand` currently set to Streamlit; may be wrong for API service |
| `app/main.py` | CORS config, `/health` endpoint, `/api/chat` handler |
| `ui/streamlit_app.py` | `API_BASE` reading (line 26), `API_URL` construction (line 27), `call_api()` function |
| `docs/deployment-plan.md` | Deployment runbook, bootstrap strategy |
| `app/config.py` | `CHROMA_PATH`, `COLLECTION_NAME`, `RATE_LIMIT` resolution |
| `ingestion/run.py` | Ingestion entrypoint called by `startCommand` |

---

## Next Investigation

**Single highest-EV next test:**

Open Railway dashboard → click `mf-faq-chatbot-v2-clean` service → **Deploy Logs** → read startup lines.

| Observed output | Conclusion | Action |
|----------------|-----------|--------|
| `You can now view your Streamlit app in your browser` | API service is running Streamlit (same `railway.toml` applied to both). Streamlit returns 403 for POST to unknown paths. | Override start command in Railway dashboard for `mf-faq-chatbot-v2-clean` to `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `startup: warming up BGE model and ChromaDB` | API is running correctly. Root cause is elsewhere — inspect HTTP logs for the API service. | Investigate Railway HTTP logs for `mf-faq-chatbot-v2-clean` |
