# Investigation Ledger — MF FAQ Chatbot v2 Production Incident

**Incident:** HTTP 403 on `POST /api/chat` from Streamlit frontend to FastAPI backend  
**Opened:** 2026-06-05  
**Status:** Fix committed and pushed. Two Railway dashboard actions remaining before production is operational. See DEPLOYMENT_HANDOFF.md operator checklist.

---

## FACTS

---

**FACT-001**  
**Description:** Streamlit frontend service (`adventurous-inspiration`) is running Streamlit, not FastAPI/uvicorn.  
**Evidence:** Railway Deploy Logs for deployment ac118735 show: `Collecting usage statistics. To deactivate, set browser.gatherUsageStats to false.` and `You can now view your Streamlit app in your browser. URL: http://0.0.0.0:8080` — these are Streamlit startup messages.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-002**  
**Description:** Streamlit service binds to port 8080 inside its Railway container.  
**Evidence:** Deploy logs line: `URL: http://0.0.0.0:8080`  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-003**  
**Description:** Streamlit service health check at path `/health` passes.  
**Evidence:** Railway build logs, deployment ac118735: `Path: /health`, `Retry window: 5m0s`, `[1/1] Healthcheck succeeded!`  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-004**  
**Description:** `API_BASE` is set on the `adventurous-inspiration` service to `http://mf-faq-chatbot-v2-clean.railway.internal:8080`.  
**Evidence:** Railway Variables tab screenshot — `API_BASE` row is unmasked and fully readable.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-005**  
**Description:** The full URL being requested at runtime is `http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat`.  
**Evidence:** Error message visible in Streamlit UI: `403 Client Error: Forbidden for url: http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat`. This matches `API_URL = f"{API_BASE}/api/chat"` (line 27, `ui/streamlit_app.py`).  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-006**  
**Description:** The 403 is returned from Railway's private network (`railway.internal`), not the public internet.  
**Evidence:** The URL in FACT-005 uses `.railway.internal` — this is Railway's internal DNS, not Cloudflare or any public proxy.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-007**  
**Description:** `railway.toml` `startCommand` is currently `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0`.  
**Evidence:** `railway.toml` at HEAD (`72ad5e1`) in the repository. Commit `21a68ba` introduced this change.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-008**  
**Description:** `railway.toml` contains a stale comment claiming "startCommand runs ingestion before uvicorn" — this contradicts the actual `startCommand` which runs Streamlit.  
**Evidence:** `railway.toml` lines 3–4 (comment) vs line 21 (actual `startCommand`).  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-009**  
**Description:** The FastAPI application code (`app/main.py`) has no code path that returns HTTP 403.  
**Evidence:** All response paths in `app/main.py`: 200 (with `is_refusal` flag), 422 (body parse failure), 429 (rate limit via slowapi). No 403 exists.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-010**  
**Description:** Port 8080 on `mf-faq-chatbot-v2-clean.railway.internal` is accepting TCP connections and returning HTTP responses.  
**Evidence:** An HTTP 403 response was received. A 403 is a valid HTTP response — it proves the TCP connection was established and something responded. A closed port or wrong hostname would produce a `ConnectionError`, not an HTTP status code.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-011**  
**Description:** Both Railway services are deployed from the same GitHub repository (`sankalp305zeus/mf-faq-chatbot-v2-clean`, branch `main`).  
**Evidence:** Railway service detail panel shows "Deployed via GitHub: sankalp305zeus/mf-faq-clean → main". Both service cards in Railway canvas show GitHub icon.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-012**  
**Description:** The `adventurous-inspiration` service's previous deployment (9eb048a5) used start command `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. That deployment is no longer active.  
**Evidence:** Railway deployment details panel, deployment 9eb048a5.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-013**  
**Description:** The `mf-faq-chatbot-v2-clean` (API) service is running Streamlit, not FastAPI/uvicorn.  
**Evidence:** Railway Deploy Logs for `mf-faq-chatbot-v2-clean` show: `Starting Container` → `You can now view your Streamlit app in your browser. URL: http://0.0.0.0:8080` → `Collecting usage statistics...` — identical Streamlit startup sequence to the frontend service.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-014**  
**Description:** `railway.toml` has exactly one `[deploy]` block with no per-service scoping. Both Railway services read and apply the same `startCommand`.  
**Evidence:** `railway.toml` lines 15–26 — single `[deploy]` section, `startCommand = "streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0"`. Railway's `railway.toml` spec supports per-service configuration only via dashboard overrides or a `[[services]]` block; neither exists in this file. No `Dockerfile`, `Procfile`, or `nixpacks.toml` present in the repo root.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-015**  
**Description:** No `Dockerfile`, `Procfile`, `nixpacks.toml`, or `railway.json` exists in the repository. The only deployment configuration file is `railway.toml`.  
**Evidence:** `find` output across repo root and subdirectories — only `railway.toml` returned.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-016**  
**Description:** `railway.toml` comment block (lines 1–10) explicitly describes the intent as a FastAPI backend file and mentions a separate Streamlit UI service — but the `startCommand` on line 21 is Streamlit, directly contradicting the documented intent.  
**Evidence:** `railway.toml` lines 1–10 vs line 21. Comment was written for the original API-only configuration; line 21 was overwritten by commit `21a68ba` (Streamlit UI deployment) and never restored.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

## DISPROVEN

---

**DISPROVEN-001**  
**Description:** "The 403 is from Railway's Cloudflare/public edge proxy blocking `python-requests` User-Agent traffic."  
**Evidence:** FACT-006 — the 403 URL is `http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat`. Requests to `.railway.internal` addresses travel over Railway's private internal network. Cloudflare and Railway's public edge proxy are not in this path.  
**Status:** Disproven  
**Last Updated:** 2026-06-05

---

**DISPROVEN-002**  
**Description:** "`API_BASE` is not set on the Streamlit service, causing it to fall back to `http://localhost:8000`."  
**Evidence:** FACT-004 — `API_BASE` is clearly visible in the Railway Variables screenshot, set to the private network URL.  
**Status:** Disproven  
**Last Updated:** 2026-06-05

---

**DISPROVEN-003**  
**Description:** "The URL construction in `ui/streamlit_app.py` is wrong (e.g., double slash, path included in `API_BASE`)."  
**Evidence:** FACT-005 — the error message shows `http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat` which is the exact expected URL. No double slash, no malformed path.  
**Status:** Disproven  
**Last Updated:** 2026-06-05

---

**DISPROVEN-004**  
**Description:** "Nothing is listening on port 8080 at `mf-faq-chatbot-v2-clean.railway.internal` — the request fails at the TCP layer."  
**Evidence:** FACT-010 — HTTP 403 was received. This is an application-layer response, not a network error.  
**Status:** Disproven  
**Last Updated:** 2026-06-05

---

**DISPROVEN-005**  
**Description:** "`mf-faq-chatbot-v2-clean` might have a per-service start command override in the Railway dashboard that runs uvicorn — and the 403 has a different cause."  
**Evidence:** FACT-013 — deploy logs confirm Streamlit is running. If a uvicorn override existed, logs would show `Uvicorn running on http://0.0.0.0:8080` or the BGE warmup message instead.  
**Status:** Disproven  
**Last Updated:** 2026-06-05

---

## UNKNOWNS

---

**UNKNOWN-001**  
**Description:** What process is the `mf-faq-chatbot-v2-clean` service actually running — FastAPI/uvicorn or Streamlit?  
**Status:** **RESOLVED** — FACT-013 confirms Streamlit is running.  
**Last Updated:** 2026-06-05

---

**UNKNOWN-002**  
**Description:** Does the `mf-faq-chatbot-v2-clean` service have a custom start command override set in the Railway dashboard?  
**Status:** **RESOLVED** — DISPROVEN-005 confirms no override exists. Deploy logs match `railway.toml` Streamlit command exactly.  
**Last Updated:** 2026-06-05

---

**UNKNOWN-003**  
**Description:** What are the exact deploy log startup lines for `mf-faq-chatbot-v2-clean`'s current active deployment?  
**Status:** **RESOLVED** — `Starting Container` → `You can now view your Streamlit app in your browser. URL: http://0.0.0.0:8080` → `Collecting usage statistics...`  
**Last Updated:** 2026-06-05

---

**UNKNOWN-004**  
**Description:** What does `GET http://mf-faq-chatbot-v2-clean.railway.internal:8080/health` return — `{"status":"ok"}` (FastAPI) or HTML/403 (Streamlit)?  
**Status:** Unresolved — not yet tested. Lower priority now that root cause is confirmed; no longer needed to confirm root cause, only to verify fix after implementation.  
**Last Updated:** 2026-06-05

---

**UNKNOWN-005**  
**Description:** What environment variables are currently set on the `mf-faq-chatbot-v2-clean` service?  
**Status:** Unresolved — still unknown. Required before any fix is deployed (must confirm `GROQ_API_KEY`, `CHROMA_PATH`, `COLLECTION_NAME` are present on the API service, not just the frontend service).  
**Last Updated:** 2026-06-05

---

## ROOT CAUSE (Confirmed)

**Commit `21a68ba`** changed `railway.toml` `startCommand` from the uvicorn command to the Streamlit command in order to deploy the frontend service. Because `railway.toml` has a single global `[deploy]` block (no per-service scoping), this change applied to **both** Railway services on next push. `mf-faq-chatbot-v2-clean` has been running Streamlit ever since. Streamlit's Tornado HTTP server returns HTTP 403 for POST requests to paths it does not handle — including `/api/chat`.

**Startup chain for `mf-faq-chatbot-v2-clean` (current):**

```
Railway → reads railway.toml [deploy].startCommand
        → "streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0"
        → Streamlit Tornado server binds port 8080
        → POST /api/chat → 403 Forbidden
```

No Dockerfile, Procfile, or nixpacks.toml exists to override this. No Railway dashboard override exists.

---

## STARTUP COMMAND PRECEDENCE (Railway)

Railway resolves the start command in this order (highest → lowest):

1. **Railway dashboard "Start Command" override** (per-service) — not set (confirmed by FACT-013 matching `railway.toml`)
2. **`railway.toml` `[deploy].startCommand`** — ← **this is what runs** — currently Streamlit
3. **`Procfile`** — does not exist
4. **Nixpacks auto-detection** — overridden by step 2
5. **Dockerfile `CMD`** — does not exist

---

## SMALLEST FIX TO RESTORE UVICORN

**Option A — Railway dashboard override (zero code change, zero git commit)**

In Railway dashboard → `mf-faq-chatbot-v2-clean` → Settings → Deploy → Start Command, enter:

```
python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

This per-service override takes precedence over `railway.toml` and does not affect the `adventurous-inspiration` frontend service. Railway will redeploy automatically on save.

**Tradeoff:** The override lives only in the Railway dashboard. It is not tracked in git, so it is invisible to future developers and will be lost if the service is deleted and recreated.

---

**Option B — Fix `railway.toml` with per-service scoping (one git commit, redeploy required)**

Replace the global `[deploy]` block with two `[[services]]` blocks (Railway's per-service TOML syntax):

```toml
[[services]]
name = "mf-faq-chatbot-v2-clean"
[services.deploy]
startCommand = "python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3

[[services]]
name = "adventurous-inspiration"
[services.deploy]
startCommand = "streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**Tradeoff:** Git-tracked, self-documenting. Requires one commit and one redeploy of both services. Railway's support for `[[services]]` in `railway.toml` should be verified against current docs before implementation.

---

---

**FACT-017**  
**Description:** `GET https://mf-faq-chatbot-v2-clean-production.up.railway.app/health` returns Streamlit HTML, not `{"status":"ok"}`.  
**Evidence:** `curl` response is the Streamlit SPA bootstrap HTML (`<!doctype html>...<title>Streamlit</title>...`). If FastAPI were running, this endpoint returns `{"status":"ok"}` (confirmed from `app/main.py` `/health` handler). Streamlit serves its own index.html for all GET requests it does not recognise as WebSocket upgrades.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-018**  
**Description:** `POST https://mf-faq-chatbot-v2-clean-production.up.railway.app/api/chat` returns `403: Forbidden` — same error class as the private network path.  
**Evidence:** `curl -X POST .../api/chat` returns `<html><title>403: Forbidden</title><body>403: Forbidden</body></html>` — Streamlit's Tornado HTTP server responding to an unrecognised POST path. This is the public-internet equivalent of the `railway.internal` 403 already documented in FACT-005.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-019**  
**Description:** All required env vars for the API service are present in the project `.env` file: `GROQ_API_KEY`, `GROQ_MODEL`, `CHROMA_PATH`, `COLLECTION_NAME`.  
**Evidence:** `.env` contains `GROQ_API_KEY=gsk_...`, `GROQ_MODEL=llama-3.3-70b-versatile`, `CHROMA_PATH=data/index`, `COLLECTION_NAME=mf_faq`. Whether these are set on the Railway `mf-faq-chatbot-v2-clean` service is still UNKNOWN-005 — this fact only confirms their values are known and available to add if missing.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

**FACT-020**  
**Description:** Railway CLI is not authenticated on this machine. No `RAILWAY_TOKEN` or `RAILWAY_API_TOKEN` is present in the local environment, `.env`, or `~/.railway/` config directory.  
**Evidence:** `railway whoami` → `Unauthorized`. `~/.railway/` contains only `version.json` with update metadata, no auth token. `env | grep -i railway` → no results.  
**Status:** Confirmed  
**Last Updated:** 2026-06-05

---

## NEXT HIGHEST-EV EXPERIMENT

**Hard blocker: RAILWAY_API_TOKEN not available on this machine (FACT-020).**

All remaining fix steps require authenticated Railway access:
- Setting the start command override on `mf-faq-chatbot-v2-clean`
- Inspecting variables on that service (UNKNOWN-005)
- Triggering redeploy
- Watching deploy logs

**To unblock:** provide `RAILWAY_API_TOKEN` via one of:

```
# Option A — set in terminal, then re-run
export RAILWAY_API_TOKEN=<your token>

# Option B — add to .env (do NOT commit)
RAILWAY_API_TOKEN=<your token>
```

Token location: Railway dashboard → top-right avatar → **Account Settings** → **Tokens** → Create new token.

Once the token is available, the full fix sequence can execute without further manual steps.
