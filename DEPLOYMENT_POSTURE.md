# Deployment Posture — MF FAQ Chatbot v2

**As of:** 2026-06-05 — split-config fix committed and pushed
**Incident:** Active — fix deployed to git, two Railway dashboard actions pending

---

## What is working?

- Streamlit UI loads and renders at `https://adventurous-inspiration-production-7f7f.up.railway.app`
- `mf-faq-chatbot-v2-clean` service is Online and accepts TCP connections on port 8080
- Full local pipeline: 164/164 tests pass
- All application code is deployed (current HEAD pushed to `origin/main`)
- `API_BASE` env var is correctly set and correctly used in code
- `railway.toml` now contains the correct uvicorn startCommand (restored)
- `railway.ui.toml` now exists with the correct Streamlit startCommand

## What is not working?

- `POST /api/chat` still returns `403 Client Error: Forbidden` — Railway has not yet redeployed with the new config
- `GET /health` on API service returns Streamlit HTML — same reason
- End-to-end chat flow is completely broken in production until Railway redeploys

## What is assumed?

| Assumption | Basis |
|-----------|-------|
| Railway will pick up `railway.toml` for API service and `railway.ui.toml` for UI service once each service's "Railway Config File" is set in dashboard Settings | Railway docs: "You can use a custom config file by setting it on the service settings page" |
| Config-as-code overrides any dashboard start command setting | Railway docs: "Configuration defined in code will always override values from the dashboard" |
| `GROQ_API_KEY` is set on `mf-faq-chatbot-v2-clean` — not yet verified (UNKNOWN-005) | Assumed from .env presence; not confirmed in Railway Variables |

## What is proven?

- Root cause: commit `21a68ba` set `railway.toml` `startCommand` to Streamlit, applied globally to both services
- `mf-faq-chatbot-v2-clean` deploy logs: `You can now view your Streamlit app in your browser` (FACT-013)
- `GET /health` on API public URL returns Streamlit HTML, not `{"status":"ok"}` (FACT-017)
- `POST /api/chat` returns `<html><title>403: Forbidden</title>` from Streamlit Tornado (FACT-018)
- FastAPI has no 403 code path — if FastAPI were running, 403 from `/api/chat` is impossible (FACT-009)
- Dashboard start command override cannot override `railway.toml` — confirmed in Railway docs

## What evidence is still missing?

1. Variables on `mf-faq-chatbot-v2-clean` — GROQ_API_KEY presence specifically (UNKNOWN-005)

## Exact current blocker

Two Railway dashboard actions are required and cannot be automated without RAILWAY_API_TOKEN:

### Action 1 — Frontend
`adventurous-inspiration` → Settings → Railway Config File → `/railway.ui.toml` → Save

### Action 2 — Backend
`mf-faq-chatbot-v2-clean` → Variables → confirm GROQ_API_KEY present
`mf-faq-chatbot-v2-clean` → Settings → Railway Config File → `/railway.toml` (or blank) → Save

## Definition of Done

All four must pass:
1. `mf-faq-chatbot-v2-clean` deploy logs: ingestion output + `Uvicorn running on http://0.0.0.0:PORT`
2. `GET https://mf-faq-chatbot-v2-clean-production.up.railway.app/health` → `{"status":"ok"}`
3. `POST /api/chat` with `{"question":"What is the expense ratio of HDFC Flexi Cap Fund?"}` → valid JSON answer with citation
4. `https://adventurous-inspiration-production-7f7f.up.railway.app` returns a real MF FAQ answer in UI chat — no 403/500 error bubble
