# Active

Phase: Production fix — Railway split-config deployed, awaiting dashboard operator action
Agent: Maya + Sentinel + Forge
Mode: ai-rag

## Objective

Fix confirmed root cause: mf-faq-chatbot-v2-clean was running Streamlit instead of FastAPI because both Railway services shared a single railway.toml with startCommand = Streamlit.

Fix: split-config architecture — railway.toml (API/uvicorn) + railway.ui.toml (UI/Streamlit). Committed and pushed. Awaiting operator to set "Railway Config File" per service in Railway dashboard.

## Commit

fix: split Railway config per service — restore API startCommand to uvicorn
Branch: main. Push: confirmed (see commit hash in DEPLOYMENT_HANDOFF.md).

## Blocker (operator action required — cannot be automated without RAILWAY_API_TOKEN)

Two Railway dashboard actions remaining before redeployment:

1. adventurous-inspiration → Settings → Railway Config File → /railway.ui.toml → Save
2. mf-faq-chatbot-v2-clean → Settings → Railway Config File → /railway.toml (or blank) → Save + Redeploy

## Definition of Done

- mf-faq-chatbot-v2-clean deploy logs show ingestion output + "Uvicorn running"
- GET /health → {"status":"ok"}
- POST /api/chat → valid JSON answer with citation
- https://adventurous-inspiration-production-7f7f.up.railway.app loads and returns a real MF FAQ answer in chat
