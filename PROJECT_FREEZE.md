# PROJECT FREEZE — MF FAQ Assistant v2

**Status: MAINTENANCE**  
**Frozen:** 2026-06-05  
**Final commit:** `bfa2793` — docs: add project closure report and final ledger state  
**Recommendation:** MAINTENANCE — backend and frontend are both live and working. No active development. Open defects are documented and scoped. The project is portfolio-ready as-is.

---

## Final Project Status

| Component | Status |
|---|---|
| Backend API (`mf-faq-chatbot-v2-clean`) | **LIVE** — FastAPI + uvicorn, all endpoints operational |
| Frontend UI (`adventurous-inspiration`) | **LIVE** — Streamlit, health check passes, end-to-end chat working |
| Daily ingestion pipeline | **LIVE** — GitHub Actions cron at 04:30 UTC |
| All tests | 164/164 passing locally |
| Production incident | **RESOLVED** — 403 root-caused and fixed |

---

## Final Architecture

```
Offline (daily):
  GitHub Actions cron 04:30 UTC
    → python -m ingestion.run
       → requests + BeautifulSoup (__NEXT_DATA__ SSR)
       → BGE-small-en-v1.5 embeddings (local, 384-dim)
       → ChromaDB (data/index/)
    → POST RAILWAY_DEPLOY_HOOK_URL

Online (per request):
  Browser
    → Streamlit (adventurous-inspiration :8080)
       → POST http://mf-faq-chatbot-v2-clean.railway.internal:8080/api/chat
    → FastAPI (mf-faq-chatbot-v2-clean :8080)
       → PII guard → classify → retrieve → Groq generate → validate
    → {answer, citation_url, is_refusal, scheme_name}
    → Streamlit renders answer + citation + last_updated footer
```

---

## Final Deployment URLs

| Service | URL |
|---|---|
| Frontend (Streamlit) | https://adventurous-inspiration-production-7f7f.up.railway.app |
| Backend (FastAPI) public | https://mf-faq-chatbot-v2-clean-production.up.railway.app |
| Backend (FastAPI) private | http://mf-faq-chatbot-v2-clean.railway.internal:8080 |
| API docs (Swagger) | https://mf-faq-chatbot-v2-clean-production.up.railway.app/docs |
| GitHub repo | https://github.com/sankalp305zeus/mf-faq-chatbot-v2-clean |

---

## Final Commit Hash

`bfa2793` — `2026-06-05`

Full git log (recent):
```
bfa2793 docs: add project closure report and final ledger state
ea22148 fix: add missing import os to app/main.py (Railway bot)
c6997ae fix: split Railway config per service — restore API startCommand to uvicorn
94f1abb docs: add production deployment handoff package
72ad5e1 Harden CORS: configurable origins via ALLOWED_ORIGINS env var
21a68ba Fix Railway startup and deploy Streamlit frontend
9c7d967 Fix Railway deployment bootstrap for ChromaDB index
c40504c Phase 7: scheduler, deployment automation and documentation
```

---

## Known Limitations (accepted at freeze)

| ID | Limitation | Severity | Fix in |
|---|---|---|---|
| L1 | Corpus covers only 5 HDFC schemes — queries about any other scheme return a fallback with a potentially mismatched citation | Medium | v1.2 |
| L2 | Fallback answer does not set `is_refusal: true` — the field is misleading when the LLM cannot extract a specific answer | Low | v1.1 |
| L3 | ChromaDB index is rebuilt from scratch on every Railway redeploy (~80s unavailability window) | Low | v2.0 |
| L4 | No structured logging or alerting — production incidents are invisible until a user reports them | Medium | v1.2 |
| L5 | Frontend and backend deploy from same repo — a push that changes `railway.toml` can regress the frontend unless the Railway Config File dashboard field is verified | Low | v1.1 |
| L6 | `FETCH_USER_AGENT` still contains placeholder URL `+https://example.com` | Cosmetic | v1.1 |

---

## Deferred Roadmap

### v1.1 (1–2 weeks)
- Set `is_refusal: true` when LLM answer matches fallback string pattern
- Add supported schemes list in Streamlit sidebar
- Replace `FETCH_USER_AGENT` placeholder URL with live frontend URL
- Add Groww ToS compliance note to README

### v1.2 (2–4 weeks)
- Expand corpus to 15–25 URLs per scheme (KIM, SID, SEBI product label)
- Write `scheme_level last_fetched_at` to metadata; surface real freshness in UI
- Add structured logging (JSON stdout → Railway log drain → Axiom free tier)

### v2.0 (1–2 months)
- Persistent ChromaDB on Railway volume (eliminate rebuild-on-deploy)
- Evaluation harness: automated QA against ground-truth scheme facts
- Expand to multiple AMC families (Axis, Mirae, etc.)
- API versioning and multi-tenant rate limiting

---

## Lessons Learned

**1. Railway config-as-code always overrides the dashboard.**
The planned "dashboard start command override" fix was invalidated by Railway's own precedence rule. Root-causing this required reading the actual documentation, not assuming dashboard settings take precedence. Lesson: when debugging deployment config, read the platform's precedence spec before proposing fixes.

**2. A single shared config file is a single point of failure for a multi-service deployment.**
One `railway.toml` with one `[deploy]` block applies identically to every service that reads it. The fix — splitting into `railway.toml` and `railway.ui.toml` with per-service Railway Config File pointers — is architecturally simple but only discoverable from documentation, not from the error.

**3. releaseCommand in Railway is not the same as a start-time command.**
Railway's `releaseCommand` runs in an ephemeral container whose filesystem is discarded before the runtime container starts. The ChromaDB index written during release was invisible to the running server. Ingestion must run in the same process chain as the server.

**4. `is_refusal: false` on a fallback answer is worse than a 404.**
When the retriever finds no good match, the LLM returns a polite fallback string and the system tags it as `is_refusal: false`. The user sees a non-answer with a citation pointing to the wrong scheme. A clean `is_refusal: true` response would be more honest and less confusing.

**5. Corpus scope is a product decision, not a data engineering one.**
The choice of 5 schemes was deliberate — narrow corpus → higher retrieval precision. But the product didn't communicate this scope to users. A sidebar listing supported schemes would have prevented the "Flexi Cap Fund" test from surfacing as a defect.

**6. Structured root-cause analysis (FACTS / DISPROVEN / UNKNOWNS) dramatically reduces debugging time.**
The production incident was resolved without any guesswork. Every hypothesis was tested against evidence before being acted on. The INVESTIGATION_LEDGER.md format proved more effective than ad-hoc debugging.

---

*Frozen by MAYA + Sentinel + Forge — 2026-06-05*
