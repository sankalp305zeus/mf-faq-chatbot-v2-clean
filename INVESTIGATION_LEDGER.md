# Investigation Ledger — MF FAQ Chatbot v2 Production Incident

**Incident:** HTTP 403 on `POST /api/chat` from Streamlit frontend to FastAPI backend  
**Opened:** 2026-06-05  
**Status:** Active — root cause unconfirmed, next test identified

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

## UNKNOWNS

---

**UNKNOWN-001**  
**Description:** What process is the `mf-faq-chatbot-v2-clean` service actually running — FastAPI/uvicorn or Streamlit?  
**Evidence needed:** Deploy Logs for `mf-faq-chatbot-v2-clean` — startup lines. If Streamlit is running, it would explain the 403 (Streamlit returns 403 for POST requests to paths it does not recognise). If uvicorn is running, a different root cause applies.  
**Hypothesis:** Since both services deploy from the same `railway.toml` (FACT-011, FACT-007) and `railway.toml` `startCommand` is Streamlit (FACT-007), the API service is also running Streamlit — unless it has a per-service start command override in Railway dashboard.  
**Status:** Unresolved  
**Last Updated:** 2026-06-05

---

**UNKNOWN-002**  
**Description:** Does the `mf-faq-chatbot-v2-clean` service have a custom start command override set in the Railway dashboard (which would take precedence over `railway.toml`)?  
**Evidence needed:** Railway dashboard → `mf-faq-chatbot-v2-clean` → Deployments → active deployment → Details → Configuration → Start command.  
**Status:** Unresolved  
**Last Updated:** 2026-06-05

---

**UNKNOWN-003**  
**Description:** What are the exact deploy log startup lines for `mf-faq-chatbot-v2-clean`'s current active deployment?  
**Evidence needed:** Railway dashboard → `mf-faq-chatbot-v2-clean` → Deploy Logs.  
**Status:** Unresolved  
**Last Updated:** 2026-06-05

---

**UNKNOWN-004**  
**Description:** What does `GET http://mf-faq-chatbot-v2-clean.railway.internal:8080/health` return — `{"status":"ok"}` (FastAPI) or HTML (Streamlit)?  
**Evidence needed:** Can be tested from the `adventurous-inspiration` container via Railway console: `curl http://mf-faq-chatbot-v2-clean.railway.internal:8080/health`  
**Status:** Unresolved  
**Last Updated:** 2026-06-05

---

**UNKNOWN-005**  
**Description:** What environment variables are currently set on the `mf-faq-chatbot-v2-clean` service?  
**Evidence needed:** Railway dashboard → `mf-faq-chatbot-v2-clean` → Variables tab.  
**Status:** Unresolved  
**Last Updated:** 2026-06-05

---

## NEXT TEST

**Experiment:** Open Railway dashboard → click `mf-faq-chatbot-v2-clean` → Deploy Logs → read first 5 lines of active deployment.

**Cost:** 30 seconds. Zero code changes. Zero deployments.

**Decision tree:**

```
Deploy logs show Streamlit startup messages
  → UNKNOWN-001 resolved: API service is running Streamlit
  → UNKNOWN-002 resolved: no custom start command override exists
  → Root cause confirmed: both services run Streamlit from same railway.toml
  → Fix identified: set per-service start command on mf-faq-chatbot-v2-clean
    to "python -m ingestion.run && uvicorn app.main:app --host 0.0.0.0 --port $PORT"

Deploy logs show uvicorn/FastAPI startup messages
  → UNKNOWN-001 resolved: API service is running correctly
  → Root cause is elsewhere (Railway private network access control, or other)
  → Next step: inspect HTTP logs for mf-faq-chatbot-v2-clean
```
