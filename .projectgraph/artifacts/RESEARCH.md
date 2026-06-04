# Research

<!-- Add new findings at the top of Active. -->
<!-- Move stale entries to Archive — never delete them. -->

## Active

### Embedding model — BGE over paid OpenAI
**Date:** 2026-06-04
**Source:** Problem statement + architecture (Milestone RAG.docx §7); BAAI BGE model cards (sentence-transformers)
**Confidence:** high
**Status:** current
**Needs update by:** stable

**Findings:**
- `text-embedding-3-small` is paid; project rule favors free/local.
- `BGE-small-en-v1.5` (384-dim) is free, runs locally via sentence-transformers, and is sufficient for short factual chunks.
- `BGE-large-en-v1.5` (1024-dim) gives marginally better recall at higher cost/latency; overkill for ~50–150 short chunks.

**Implications:**
- Default to **BGE-small-en-v1.5**. Embedding dim must match the vector store config; switching models requires a full re-index.

---

### Vector store — ChromaDB over FAISS
**Date:** 2026-06-04
**Source:** Architecture (docx §7); Chroma/FAISS docs
**Confidence:** high
**Status:** current
**Needs update by:** stable

**Findings:**
- Corpus is tiny (5 pages → ~50–150 chunks). Raw ANN speed is irrelevant at this scale.
- Retrieval needs **metadata filtering** (filter by `scheme_name`/`source_url`, boost by `section`). FAISS has no native metadata filter; Chroma does.
- Chroma is local, file-backed, supports upsert and persistence — matches daily re-index.

**Implications:**
- Use **ChromaDB (persistent)**. Two-stage retrieval (metadata filter → semantic) is cheap and precise.

---

### LLM — Groq
**Date:** 2026-06-04
**Source:** Implementation directive (docx Prompts: "Update Groq as LLM in phase4")
**Confidence:** high
**Status:** current
**Needs update by:** stable

**Findings:**
- Groq offers fast, low-cost inference for short constrained answers (e.g. Llama-3.x models).
- Answers are ≤3 sentences and grounded — small completion budget; speed matters for p95 < 5 s.

**Implications:**
- Use **Groq** with a strict system prompt. Add a deterministic fallback (link-only response) when the LLM is unavailable or output fails validation.

---

### Chunking strategy — section-aware
**Date:** 2026-06-04
**Source:** Architecture (docx §3.5)
**Confidence:** medium
**Status:** current
**Needs update by:** after first ingestion sample

**Findings:**
- Content maps cleanly to 9 section tags (overview, expense_ratio, exit_load, minimum_investment, benchmark, tax, fund_management, investment_objective, fund_house).
- Section-aware chunks (~200–400 tokens), overlap only within the same section; keep fund-manager bios intact in one `fund_management` chunk.

**Implications:**
- Chunk per section, not per fixed window. Each chunk carries `source_url`, `scheme_name`, `section`, `last_updated` metadata for citation + footer.
- Confidence medium until real Groww HTML is parsed — section boundaries may need tuning.

---

### Scheduler — 10:00 AM IST daily
**Date:** 2026-06-04
**Source:** Implementation directive (docx Prompts: "scheduler to run at 10:00 AM IST daily")
**Confidence:** high
**Status:** current
**Needs update by:** stable

**Findings:**
- Local dev: APScheduler/cron at 10:00 IST (04:30 UTC). Repo refresh: GitHub Actions scheduled workflow (cron in UTC).
- Online API must keep serving the previous index during re-index (atomic swap).

**Implications:**
- Ingestion is a single atomic CLI job (`ingestion/run.py`); scheduler only triggers it. Log URLs fetched + chunk count; retry once on failure.

## Archive
<!-- none yet -->
