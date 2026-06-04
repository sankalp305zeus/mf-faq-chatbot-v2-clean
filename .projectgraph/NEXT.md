# Next

Phase 7 — Scheduler + Deployment
Generated: 2026-06-04 (post Maya + Sentinel pre-deployment review)

## Critical Phase 7 work (ordered — must complete all to hit exit criteria)

1. **Fix README** — update current-status table (Phases 3–6 ✅), rewrite "What works today" section, add "Running the API" (`uvicorn app.main:app --reload`) and "Running the UI" (`streamlit run ui/streamlit_app.py`) sections.
2. **Fix ARCHITECTURE.md + README tech-stack table** — change UI layer from "Static HTML/JS (`ui/index.html`)" to "Streamlit (`ui/streamlit_app.py`)" in both documents.
3. **Add `/health` endpoint to `app/main.py`** — returns `{"status": "ok"}`; required for Railway health checks.
4. **`scheduler/daily.py`** — APScheduler BlockingScheduler, cron trigger `hour=10, minute=0, timezone="Asia/Kolkata"`, calls `ingestion.run.main()`.
5. **Uncomment `APScheduler==3.10.4` in `requirements.txt`**.
6. **`.github/workflows/ingest.yml`** — GitHub Actions cron (`cron: '30 4 * * *'`), checkout + pip install + `python -m ingestion.run`, requires `GROQ_API_KEY` secret.
7. **`docs/deployment-plan.md`** — covers: required env vars, cold-start bootstrap (`python -m ingestion.run` as release command), Railway service config (start command, env vars, release command), Groq key injection, scheduler vs GitHub Actions choice, first-deploy checklist.
8. **Deploy to Railway** — configure release command (ingestion bootstrap), start command (uvicorn or streamlit), inject env vars (GROQ_API_KEY, CHROMA_PATH, etc.).
9. **Verify live URL** — run the 5 smoke queries end-to-end against the deployed instance.
10. **Update README with live demo URL and screenshot**.

## Documentation hygiene (same session, lower priority)

- Reconcile rate limit: verify `app/config.py` default and update `.env.example` comment to match
- Replace `FETCH_USER_AGENT` placeholder `+https://example.com` with real deployed URL
- Add Groww ToS disclaimer note to README and/or deployment-plan.md
- Consider moving `Milestone RAG.docx` from repo root to `docs/`

## Future backlog — Phase 8

- FAR-08: Expand corpus from 5 to 15–25 URLs (KIM, SID, AMFI, SEBI pages per scheme)
- FAR-09: Write `scheme_level last_fetched_at` to metadata index in `ingestion/index.py`; surface real scheme freshness in `last_updated` footer instead of chunk fetch date
- Surface `supported_schemes` list in Streamlit UI for unresolved-scheme refusals (UX gap)
- Explicit CORS configuration in `app/main.py` (currently FastAPI default = allow all origins)
- Error state rendering in UI for Groq timeout / API outage
