# OS Feedback

Append-only log of agent observations about ProjectGraph OS process quality.

---

## 2026-06-04 — Pre-deployment review (Maya + Sentinel)

### What worked well
- Five-agent pipeline (Maya → Atlas → Forge → Sentinel) produced clean phase handoffs with explicit FARs raised and resolved per phase.
- Sentinel FAR system (P3, P4, P5) caught real defects before they accumulated — none carried forward unresolved within a phase.
- SUMMARY.md "Known risks" section is genuinely useful as a rolling risk register; it caught FAR-08 and FAR-09 before the review did.
- ACTIVE.md "Last decision" field preserved non-obvious decisions (classifier priority ordering, slowapi body-parsing conflict) that would have been invisible in git history alone.

### Process gaps observed

**Architecture document drift:** ARCHITECTURE.md was not updated when the UI technology changed from "Static HTML/JS (`ui/index.html`)" to Streamlit (`ui/streamlit_app.py`). This created a visible inconsistency visible to any external reviewer reading the repo. Recommendation: Atlas should own ARCHITECTURE.md updates at each phase boundary, not just at design time. Forge should flag architecture drift as a FAR if the implementation diverges from the architecture document.

**README staleness:** README.md was not updated after Phase 6. The current-status table and "What works today" section described a state two phases behind reality. Recommendation: README update should be an explicit exit criterion checklist item for every phase that changes user-visible behaviour (Phases 5, 6, 7).

**NEXT.md left empty:** The NEXT.md file was empty entering the pre-deployment review, meaning there was no machine-readable task list for Phase 7 prior to this review. Recommendation: Forge should populate NEXT.md at the end of each phase with the next phase's ordered task list, not leave it blank until the next agent activates.

**Phase 7 scope underspecified in ACTIVE.md:** ACTIVE.md described Phase 7 as a single line ("scheduler/daily.py, GitHub Actions ingest.yml, Railway deployment, docs/deployment-plan.md, README") with no ordering, no cold-start bootstrap item, no /health endpoint requirement. The review surfaced C2 (no cold-start bootstrap) and C6 (no /health endpoint) as gaps not previously captured. Recommendation: deployment phases should require an explicit "first-deploy runbook" exit criterion, since data/index/ being gitignored means every fresh deploy fails until ingestion runs.

**Corpus scope gap not escalated:** FAR-08 (5 URLs vs 15–25 in Milestone RAG.docx) has been in Known Risks since Phase 1 and has not been escalated to Maya for scope decision. It is logged as Phase 8 backlog but the PRD owner (Maya) has not formally acknowledged the descope. Recommendation: open FARs that represent scope reductions vs. the milestone spec should be explicitly acknowledged by Maya in a journal entry, not silently deferred.
