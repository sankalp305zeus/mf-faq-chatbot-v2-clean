# Active

Phase: Production incident — deployment freeze
Agent: Scribe + Maya (checkpoint)
Mode: ai-rag

## Objective
Production incident active. Streamlit UI returns `403 Client Error: Forbidden for url: http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat`. Deployment checkpoint created. No debugging or fixes permitted until ledger is reviewed and next experiment is run.

## Last handoff
Files created: DEPLOYMENT_HANDOFF.md, INVESTIGATION_LEDGER.md, DEPLOYMENT_POSTURE.md — 2026-06-05.
Commit: docs: add production deployment handoff package. Branch: main. Push: confirmed.

## Last decision
Deployment frozen. All findings documented. Single highest-EV next test identified: open Railway dashboard → mf-faq-chatbot-v2-clean → Deploy Logs → confirm whether the API service is running Streamlit or uvicorn. This resolves UNKNOWN-001 and either confirms or disproves the primary hypothesis (both services running Streamlit due to shared railway.toml).

## Blocker
CRITICAL: POST /api/chat returns 403 in production. mf-faq-chatbot-v2-clean service is suspected to be running Streamlit (not FastAPI) because both services deploy from the same railway.toml, which currently has startCommand = "streamlit run ui/streamlit_app.py ...". Root cause unconfirmed pending next test.

## Known discrepancy
railway.toml comment says "startCommand runs ingestion before uvicorn" but the actual startCommand is "streamlit run ui/streamlit_app.py ...". This inconsistency must be resolved before next deploy.

## Next
1. EXPERIMENT (no code, no deploy): Open Railway → mf-faq-chatbot-v2-clean → Deploy Logs → read startup lines
2. If Streamlit confirmed: set per-service start command override in Railway dashboard for mf-faq-chatbot-v2-clean to "python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
3. If uvicorn confirmed: inspect HTTP logs for mf-faq-chatbot-v2-clean for alternative root cause
