# Next

Phase: Post-fix verification — production incident
Generated: 2026-06-05 (post Maya + Sentinel + Forge split-config fix)

## Status: Code fix pushed. Operator dashboard actions pending.

---

## Immediate operator checklist (in order)

### Step 1 — Verify backend variables
Railway dashboard → mf-faq-chatbot-v2-clean → Variables tab.
Confirm present: GROQ_API_KEY, GROQ_MODEL, CHROMA_PATH, COLLECTION_NAME.
If missing: add from .env values (GROQ_MODEL=llama-3.3-70b-versatile, CHROMA_PATH=data/index, COLLECTION_NAME=mf_faq).

### Step 2 — Set Railway Config File on frontend service
Railway dashboard → adventurous-inspiration → Settings → General → "Railway Config File".
Set to: /railway.ui.toml
Save.

### Step 3 — Set Railway Config File on backend service
Railway dashboard → mf-faq-chatbot-v2-clean → Settings → General → "Railway Config File".
Set to: /railway.toml (or leave blank — Railway reads railway.toml by default).
Save. This triggers a redeploy of the API service.

### Step 4 — Watch backend deploy logs
Railway dashboard → mf-faq-chatbot-v2-clean → Deploy Logs.
Expected: ingestion fetch lines → ChromaDB build → "Uvicorn running on http://0.0.0.0:PORT"
Abort signal: "You can now view your Streamlit app in your browser" → config file field not saved.

### Step 5 — Test backend /health
curl https://mf-faq-chatbot-v2-clean-production.up.railway.app/health
Expected: {"status":"ok"}

### Step 6 — Test backend /api/chat
curl -s -X POST https://mf-faq-chatbot-v2-clean-production.up.railway.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the expense ratio of HDFC Flexi Cap Fund?"}'
Expected: JSON with answer, citation, is_refusal: false.

### Step 7 — Redeploy frontend (triggers pick-up of railway.ui.toml)
Railway dashboard → adventurous-inspiration → Deployments → Redeploy latest.

### Step 8 — Verify frontend
Open https://adventurous-inspiration-production-7f7f.up.railway.app
Submit: "What is the expense ratio of HDFC Flexi Cap Fund?"
Expected: answer ≤3 sentences with Groww citation. No 403/500 error bubble.

---

## Phase 8 backlog (does not block deployment)

- FAR-08: Expand corpus from 5 to 15–25 URLs
- FAR-09: Write scheme_level last_fetched_at to metadata index
- Surface supported_schemes list in Streamlit UI for unresolved-scheme refusals
- Replace FETCH_USER_AGENT placeholder URL with real deployed URL
- Add Groww ToS disclaimer to README
