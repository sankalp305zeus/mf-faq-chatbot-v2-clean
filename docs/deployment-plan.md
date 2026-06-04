# Deployment Plan — MF FAQ Assistant

Last updated: 2026-06-04

---

## Overview

The application has two runtime processes:

| Service | Technology | Purpose |
|---------|-----------|---------|
| **API** | FastAPI + uvicorn | `POST /api/chat`, `GET /health` |
| **UI** | Streamlit | Chat interface; calls the API |

Both are deployed as separate Railway services. The Streamlit service points to the API service via the `API_BASE` environment variable.

---

## Prerequisites

| Requirement | Where to get |
|-------------|-------------|
| Groq API key | console.groq.com → API Keys |
| Railway account | railway.app |
| GitHub repository pushed | `git push origin main` |

---

## Environment variables

### API service (required)

| Variable | Example value | Notes |
|----------|--------------|-------|
| `GROQ_API_KEY` | `gsk_…` | Required for generation path |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Default if unset |
| `CHROMA_PATH` | `data/index` | Relative to repo root |
| `COLLECTION_NAME` | `mf_faq` | ChromaDB collection name |
| `RATE_LIMIT` | `30/minute` | Per-IP cap (slowapi) |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose output |
| `FETCH_USER_AGENT` | `Mozilla/5.0 (compatible; mf-faq-bot/0.1; +https://<your-api-url>)` | Replace placeholder before deploy |

### UI service (required)

| Variable | Example value | Notes |
|----------|--------------|-------|
| `API_BASE` | `https://mf-faq-api.up.railway.app` | Railway URL of the API service |

---

## ChromaDB bootstrap — cold-start strategy

`data/index/` is gitignored. A fresh Railway deploy has no index. The
`releaseCommand` in `railway.toml` runs `python -m ingestion.run` before
the server starts, seeding the index automatically.

**Timeline:**
- First deploy: ~80 s (BGE model downloads from HuggingFace Hub, then ingestion runs)
- Subsequent deploys: ~19 s (model cached in Railway's build layer)

**If the release command fails**, Railway will not promote the new deploy
and the previous deployment continues serving traffic. Check the release
logs in the Railway dashboard.

**Manual bootstrap** (local or Railway shell):
```bash
python -m ingestion.run          # full fetch + parse + embed + index
python -m ingestion.run --skip-fetch  # re-index from cached HTML
```

---

## Railway deployment — step by step

### Service 1: API backend

1. Create a new Railway project → **Deploy from GitHub repo**.
2. Select this repository.
3. Railway auto-detects `railway.toml` and uses:
   - **Release command:** `python -m ingestion.run`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health check path:** `/health`
4. Add environment variables (see table above). At minimum: `GROQ_API_KEY`.
5. Deploy. Watch the release logs — ingestion should complete before the
   server starts.
6. Copy the generated Railway URL (e.g. `https://mf-faq-api.up.railway.app`).
7. Verify: `curl https://mf-faq-api.up.railway.app/health` → `{"status":"ok"}`

### Service 2: Streamlit UI

1. In the same Railway project, click **New Service** → **Deploy from GitHub repo**.
2. Select the same repository.
3. Override the start command in Railway settings:
   ```
   streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0
   ```
4. Add environment variable: `API_BASE=https://<api-service-url>`.
5. Deploy. The UI will be available at the Railway-assigned URL.

---

## Daily corpus refresh

GitHub Actions is the scheduler. The complete end-to-end refresh path is:

```
GitHub Actions cron (04:30 UTC = 10:00 AM IST)
  → python -m ingestion.run        (verify ingestion succeeds; produce audit artifact)
  → POST RAILWAY_DEPLOY_HOOK_URL   (only fires if ingestion succeeded)
      → Railway runs releaseCommand: python -m ingestion.run
      → Railway starts new deployment with freshly built index
      → live service serves updated data
```

### Required secrets

Add both as **repository secrets** in GitHub:
Settings → Secrets and variables → Actions → New repository secret.

| Secret | How to get it |
|--------|--------------|
| `GROQ_API_KEY` | console.groq.com → API Keys |
| `RAILWAY_DEPLOY_HOOK_URL` | Railway dashboard → your API service → Settings → Deploy Hooks → Create hook → copy URL |

### How the Railway deploy hook works

When GitHub Actions POSTs to the deploy hook URL, Railway:
1. Pulls the latest commit from the connected GitHub branch.
2. Builds the service (Nixpacks).
3. Runs `releaseCommand = "python -m ingestion.run"` — fetches fresh data from Groww and rebuilds the ChromaDB index.
4. Promotes the new deployment; traffic shifts to it once `/health` returns 200.
5. If the release command fails, Railway does not promote the new deployment and the previous version continues serving.

### Failure behaviour

| Failure point | Behaviour |
|---------------|-----------|
| Ingestion fails in GitHub Actions | `ingest.yml` exits non-zero; Railway deploy hook is **not** triggered; live service unchanged |
| Railway deploy hook POST fails | `ingest.yml` exits non-zero; GitHub Actions run marked as failed |
| Railway `releaseCommand` fails | Railway does not promote; previous deployment stays live |

### If `RAILWAY_DEPLOY_HOOK_URL` is not set

The workflow logs a warning and exits cleanly (exit 0). This allows the workflow to run
in forks or before Railway is configured without blocking the CI run. Once the secret is
added, the live refresh path activates automatically.

### Local / ad-hoc scheduler

`scheduler/daily.py` (APScheduler) provides a local alternative for development:
```bash
python -m scheduler.daily   # fires ingestion at 10:00 AM IST locally
```
This does not affect the live Railway deployment.

---

## Smoke test checklist (post-deploy)

Run these against the live API URL:

```bash
BASE=https://<your-api-url>

# Health check
curl $BASE/health

# Factual query
curl -s -X POST $BASE/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the expense ratio of HDFC Mid Cap Fund?"}' | python3 -m json.tool

# Advisory refusal
curl -s -X POST $BASE/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Should I invest in HDFC Small Cap Fund?"}' | python3 -m json.tool

# Comparison refusal
curl -s -X POST $BASE/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Which is better, HDFC Mid Cap or Large Cap?"}' | python3 -m json.tool

# PII guard
curl -s -X POST $BASE/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"My PAN is ABCDE1234F, what is the exit load?"}' | python3 -m json.tool
```

Expected: factual query returns `is_refusal: false` with a `citation_url`; all
others return `is_refusal: true`.

---

## Known limitations and risks

| Risk | Mitigation |
|------|-----------|
| `mfServerSideData` key path is Groww-internal; Groww may rename keys | `MissingRequiredField` is raised on parse failure — ingestion fails loudly, not silently |
| BGE model cold-start on first deploy (~80 s) | Railway `healthcheckTimeout = 300` allows time |
| ChromaDB index is ephemeral on Railway (rebuilt each deploy) | Daily Actions artifact provides a record; index is rebuilt automatically by release command |
| Corpus = 5 Groww pages; other HDFC schemes return "unresolved scheme" | Expected behaviour; covered funds listed in UI left column |
| Groww scraping uses undocumented `__NEXT_DATA__` payload | For portfolio/demo use only; not a production data pipeline |

---

## Rollback

Railway keeps previous deployments. To roll back: Railway dashboard →
Deployments → select the previous successful deployment → Redeploy.
