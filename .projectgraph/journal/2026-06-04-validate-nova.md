# Handoff

Phase: validate
Agent: Nova
Date: 2026-06-04
Confidence: high

## Objective
Validate technology choices for the RAG pipeline and record sourced findings.

## Completed
- artifacts/RESEARCH.md with 5 findings: embeddings, vector store, LLM, chunking, scheduler

## Decisions
- Embeddings = BGE-small-en-v1.5 (free/local) — paid OpenAI rejected per project rule
- Vector store = ChromaDB — needs metadata filtering + upsert; FAISS lacks native filters
- LLM = Groq — fast/cheap for short constrained answers; deterministic fallback required
- Chunking = section-aware (~200–400 tokens), bios kept intact
- Scheduler = 10:00 AM IST daily (APScheduler/cron + GitHub Actions)

## Risks
- Chunking confidence medium until real Groww HTML parsed — section boundaries may shift
- Groww HTML may be JS-rendered → may need Playwright over requests/BeautifulSoup

## Artifacts updated
- .projectgraph/artifacts/RESEARCH.md

## Next
Agent: Atlas
Action: Produce ARCHITECTURE.md (layers, data contracts, flows, tech, cross-cutting) and the phased implementation plan.
Gate: none
Escalate to: none
Status: ready
