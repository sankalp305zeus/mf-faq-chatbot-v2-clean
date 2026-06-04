# Active

# Active

Phase: Phase 7 — COMPLETE
Agent: Forge (impl) · Sentinel (review — no FARs)
Mode: ai-rag

## Objective
Phase 7 complete (2026-06-04). All six critical findings (C1–C6) from the Maya + Sentinel pre-deployment review resolved. 164 tests pass. Project is deployment-ready pending live Railway deploy and live URL confirmation.

## Last handoff
File: Phase 7 scheduler wiring fix, 2026-06-04.
Deliverables: ingest.yml updated with Railway deploy hook step (POST RAILWAY_DEPLOY_HOOK_URL secret after ingestion succeeds; graceful skip if secret not set; non-zero exit if hook POST fails). docs/deployment-plan.md "Daily corpus refresh" section replaced with complete end-to-end path documentation, failure behaviour table, and deploy hook setup instructions. README deployment section updated with full pipeline diagram and two-secret requirement.

## Last decision
GitHub Actions is the scheduler. The broken link (GH Actions built index in ephemeral runner but never updated Railway) is closed by adding a Railway deploy hook POST as the final workflow step, conditional on ingestion success. Railway's existing releaseCommand (python -m ingestion.run) handles the live index rebuild — no changes to railway.toml required. Sentinel review: no FARs.

## Blocker
None. Remaining open items are Phase 8 backlog (FAR-08 corpus expansion, FAR-09 last_fetched_at, supported_schemes UX, CORS explicit config) — none block deployment.

## Next
Phase 8 backlog (optional):
- FAR-08: Expand corpus to 15–25 URLs (KIM/SID/AMFI/SEBI)
- FAR-09: Write scheme-level last_fetched_at to metadata index
- Surface supported_schemes in UI on unresolved-scheme refusal
- Explicit CORS config in app/main.py
- Replace FETCH_USER_AGENT placeholder with live deployed URL
