# Deployment Posture — MF FAQ Chatbot v2

**As of:** 2026-06-05  
**Incident:** Active — 403 on API calls from Streamlit frontend

---

## What is working?

- Streamlit UI loads and renders at `https://adventurous-inspiration-production-7f7f.up.railway.app`
- Streamlit service starts successfully on port 8080 and passes Railway health check
- `mf-faq-chatbot-v2-clean` service is Online (Railway canvas) and accepts TCP connections on port 8080
- Full local pipeline: 164/164 tests pass
- All application code is deployed (current HEAD `72ad5e1` pushed to `origin/main`)
- `API_BASE` environment variable is correctly set and correctly used in code

## What is not working?

- `POST /api/chat` returns `403 Client Error: Forbidden` — no user questions can be answered
- End-to-end chat flow is completely broken in production

## What is assumed?

| Assumption | Basis |
|-----------|-------|
| The API service (`mf-faq-chatbot-v2-clean`) is running Streamlit instead of uvicorn | Both services use same `railway.toml`; `railway.toml` `startCommand` is currently Streamlit; no evidence of a per-service override |
| Port 8080 is consistent across both services | Railway default `$PORT` is typically 8080; confirmed for Streamlit service |
| The 403 comes from Streamlit's internal HTTP server rejecting a POST to an unknown path | Streamlit's Tornado-based server returns 403 for POST requests to paths it does not handle |

## What is proven?

- The 403 URL is `http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat` — confirmed from UI error
- Something is listening on port 8080 at that internal address and returning HTTP (not a network failure)
- FastAPI application code has no 403 path — if FastAPI were running, 403 would be impossible from application logic
- `railway.toml` `startCommand` = Streamlit — confirmed from repo
- Streamlit service runs Streamlit — confirmed from Railway deploy logs

## What is the exact current blocker?

The `mf-faq-chatbot-v2-clean` service appears to be running Streamlit (not FastAPI/uvicorn) because both services deploy from the same `railway.toml`, which currently has `startCommand = "streamlit run ui/streamlit_app.py ..."`. Streamlit's internal HTTP server returns 403 for POST requests to `/api/chat` because it does not recognise that path. The FastAPI API is not running in production.

## What evidence is missing?

1. Deploy Logs for `mf-faq-chatbot-v2-clean` — what process actually starts
2. Start command override (if any) in Railway dashboard for `mf-faq-chatbot-v2-clean`
3. Variables on `mf-faq-chatbot-v2-clean` service

## What is the single highest-value next test?

**Open Railway dashboard → `mf-faq-chatbot-v2-clean` → Deploy Logs → read startup lines.**

If the logs show `You can now view your Streamlit app in your browser` → root cause is confirmed, fix is to set a per-service start command override in Railway dashboard for `mf-faq-chatbot-v2-clean` to `python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

This test takes 30 seconds, requires no code changes, and resolves the primary unknown.
