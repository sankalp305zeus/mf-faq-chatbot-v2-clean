# Handoff

Phase: discover
Agent: Maya
Date: 2026-06-04
Confidence: high

## Objective
Frame the Mutual Fund FAQ Assistant, set mode and scope, and produce the PRD.

## Completed
- Repurposed CONTEXT.md from OS-template to the MF FAQ Assistant project
- Authored artifacts/PRD.md (problem, users, in/out scope, corpus, response contract, compliance, success criteria)
- Set Mode: ai-rag

## Decisions
- Mode = ai-rag — retrieval + eval + compliance gating justify the full 5-phase pipeline
- Corpus fixed to the 5 HDFC Groww URLs from the milestone doc
- Facts-only contract: ≤3 sentences + 1 allowlisted citation + last-updated footer

## Risks
- Groww is reference context, not HDFC primary docs (KIM/SID) — scope limitation, not a defect
- Vague scheme references may need disambiguation

## Artifacts updated
- .projectgraph/CONTEXT.md
- .projectgraph/artifacts/PRD.md

## Next
Agent: Nova
Action: Validate embedding model, vector store, LLM, chunking, and scheduler choices; record in artifacts/RESEARCH.md.
Gate: none
Escalate to: none
Status: ready
