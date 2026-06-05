# PM Case Study — MF FAQ Assistant v2

**Project:** MF FAQ Assistant  
**Role:** Product Manager + Engineer (solo)  
**Duration:** ~4 weeks (Phases 1–7 + deployment)  
**Status:** Live in production — 2026-06-05  
**Live URL:** https://adventurous-inspiration-production-7f7f.up.railway.app

---

## 1. Problem

Retail investors in India looking up basic scheme facts — expense ratio, exit load, fund manager, minimum investment amount — face a fragmented, high-friction experience.

The information exists. HDFC AMC publishes it. Groww aggregates it. But:

- Each fact requires navigating to a specific page
- Pages are dense with marketing content surrounding small data points
- Looking up the same fact across 3 schemes requires 3 separate page loads
- There is no natural-language interface — users must know where to look

A typical lookup takes 3–5 minutes. For an investor comparing 3 schemes across 4 parameters, that's 12–20 minutes of low-value page navigation before any analytical thinking begins.

---

## 2. Research

**Observation method:** Personal pain + informal user interviews with 4 retail investors in the researcher's network.

**Key findings:**
- All 4 investors used Groww or ET Money as their primary lookup tool
- All 4 described "finding expense ratio" as a multi-step process: search scheme → scroll past NAV/returns → find details tab → find expense ratio row
- 3 of 4 had encountered outdated information on aggregator sites (scheme details page not refreshed after quarterly TER update)
- 0 of 4 had ever read a KIM or SID document; all relied on aggregator summaries
- Common advisory queries: "should I invest?", "which is better?", "is this a good fund?" — these require judgment, not lookup

**Competitive landscape:**
- Groww / ET Money: dense pages, no Q&A interface, no citation for individual facts
- ChatGPT: answers advisory queries but hallucinated expense ratios in testing (cited numbers not matching current Groww data)
- AMC websites: authoritative but extremely difficult to navigate for a specific fact

**Gap identified:** No product offers a fast, natural-language, cited, facts-only answer for scheme-level data.

---

## 3. User Insights

**Primary persona — Priya, 28, software engineer, Mumbai**
- Invests ₹10,000/month in 2–3 mutual funds via Groww
- Makes scheme decisions 2–3 times per year (new SIP, scheme switch, top-up decision)
- Comfortable with digital products; uncomfortable with financial jargon
- Pain point: "I just want to know the expense ratio and exit load before I decide. Why do I have to scroll through so much?"

**Secondary persona — Arjun, 35, business analyst, Bangalore**
- More financially literate; already knows what to look for
- Pain point: speed. "I don't need to be educated. I just need the number."

**Out-of-scope persona (deliberately excluded):**
- First-time investor needing guidance on *which* fund to choose — this requires advisory, which the product explicitly refuses

---

## 4. Opportunity

A facts-only RAG chatbot scoped to a defined corpus of scheme pages could:
- Reduce lookup time from 3–5 minutes to <10 seconds
- Ground every answer in a verifiable source (citation URL)
- Eliminate the advisory risk by refusing guidance queries
- Refresh automatically so data is never more than 24 hours stale

**Why RAG, not a database:**
Scheme fact pages are semi-structured HTML with variable layouts. A database would require structured extraction that breaks when Groww changes page layout. RAG tolerates layout variation because it retrieves by semantic similarity, not field mapping.

**Why not just scrape and display:**
A display layer without language understanding can't map "who manages this fund" to the fund manager section. The LLM step is necessary to extract a natural-language answer from retrieved text chunks.

---

## 5. Solution

**MF FAQ Assistant** — a retrieval-augmented generation chatbot that:

1. Ingests 5 HDFC scheme pages from Groww daily
2. Embeds chunks using BGE-small-en-v1.5 (local inference)
3. On each user query: retrieves semantically relevant chunks → generates a ≤3-sentence factual answer via Groq (Llama-3.3-70b) → returns the answer with a citation URL
4. Refuses advisory, comparison, and performance queries by design
5. Guards against PII input (PAN-like patterns)

**Core product decision:** every answer must be a verifiable fact tied to a source. The product is a lookup tool, not an advisor.

---

## 6. Architecture

```
OFFLINE (daily, automated):
  GitHub Actions cron (04:30 UTC)
  → Fetch 5 Groww scheme pages (requests + BeautifulSoup)
  → Extract structured content from __NEXT_DATA__ SSR JSON
  → Generate overlapping text chunks
  → Embed with BGE-small-en-v1.5 (local, no API cost)
  → Store in ChromaDB
  → Trigger Railway redeploy via deploy hook

ONLINE (per user query):
  Streamlit UI → FastAPI → PII guard → classify query →
  retrieve top-k chunks → Groq Llama-3.3-70b →
  validate output → return {answer, citation_url, is_refusal}
```

**Stack:** Python · FastAPI · ChromaDB · BGE-small · Groq · Streamlit · Railway · GitHub Actions

---

## 7. MVP Scope

**In scope (shipped):**
- 5 HDFC schemes (Mid Cap, Large Cap, Small Cap, Gold ETF FoF, Defence)
- Query types: expense ratio, exit load, fund manager, minimum investment, AUM, fund objective
- Advisory refusal (investment advice, comparisons, performance projections)
- PII guard (blocks PAN-like inputs)
- Rate limiting (20 req/min)
- Daily ingestion with automated Railway redeploy
- Citation on every answer
- Source freshness timestamp in UI footer

**Explicitly out of scope (v1):**
- Multiple AMC families
- Historical performance data
- Comparison queries
- User accounts or query history
- Mobile-native interface

**Why these boundaries:**
Narrow corpus → higher retrieval precision. Advisory exclusion → no regulatory risk. No auth → no barrier to first use. Every out-of-scope item was a deliberate prioritization call, not an oversight.

---

## 8. Tradeoffs

| Decision | Option A (chosen) | Option B (not chosen) | Why A |
|---|---|---|---|
| Corpus size | 5 schemes | All HDFC schemes (~40) | Precision > breadth for v1; larger corpus degrades retrieval quality |
| Embeddings | BGE-small (local) | OpenAI text-embedding-3-small | No per-query API cost; no external dependency |
| Generation | Groq Llama-3.3-70b | OpenAI GPT-4o | Free tier; sufficient for factual extraction |
| Frontend | Streamlit | React/Next.js | Speed to ship; acceptable UX ceiling for v1 |
| Data store | ChromaDB in-process | Pinecone / Weaviate | No external vector DB cost; simpler for solo deployment |
| Advisory queries | Refuse entirely | Answer with disclaimers | Regulatory safety; prevents LLM from acting as financial advisor |
| Ingestion timing | At container startup | As releaseCommand | Railway releaseCommand runs in ephemeral container; filesystem discarded before server starts |

---

## 9. Results

**Production metrics (at freeze, 2026-06-05):**

| Metric | Value |
|---|---|
| API response time | <5 seconds per query |
| In-corpus query accuracy | 6/7 test queries pass (correct answer + correct citation) |
| Out-of-corpus handling | 1 defect — fallback answer with mismatched citation |
| Advisory refusal | 100% — all advisory queries refused with `is_refusal: true` |
| Uptime since fix | 100% (backend) |
| Production incidents | 1 (403 error) — root-caused and resolved |
| Test coverage | 164/164 locally |
| Deployment time (cold start) | ~80s first deploy (BGE download); ~19s subsequent |

**Qualitative outcomes:**
- Time to answer for in-corpus scheme facts: <10 seconds vs. 3–5 minutes (manual)
- Every answer is source-cited — verifiability is built-in
- Advisory risk is zero — the product cannot be prompted into giving investment advice

---

## 10. Lessons Learned

**Product:**
1. Corpus scope is a product decision. Communicating scope to users (sidebar listing supported schemes) is a UX decision that prevents user frustration and support burden.
2. "I don't have that information" with a wrong citation is worse than "I don't know." Fallback responses need as much design attention as success responses.
3. Advisory refusal is not just a safety feature — it's a positioning decision. It tells users exactly what the product is and isn't.

**Technical:**
4. RAG retrieval quality is more sensitive to corpus breadth than to model size. Adding 40 schemes without improving chunking strategy would have degraded answer quality.
5. Railway's config-as-code always overrides dashboard settings. Platform documentation must be read before proposing infrastructure fixes.
6. A shared deployment config file across multiple services is a latent production incident. Per-service config files are the correct architecture from day one.

**Process:**
7. Evidence-based root cause analysis (FACTS / DISPROVEN / UNKNOWNS format) is faster than trial-and-error debugging. Every hypothesis test was documented; no hypothesis was acted on without evidence.
8. "Freeze before debug" — creating a deployment checkpoint before attempting fixes prevented overwriting working state with broken changes.

---

## 11. Future Roadmap

### Near-term (v1.1 — 1–2 weeks)
- Fix fallback `is_refusal` flag
- Add supported schemes list in Streamlit sidebar
- Structured JSON logging

### Medium-term (v1.2 — 2–4 weeks)
- Expand to 15–25 URLs per scheme (KIM, SID, SEBI product label)
- Real freshness timestamp from scheme metadata
- Axiom/Datadog free-tier log drain

### Long-term (v2.0 — 1–2 months)
- Persistent ChromaDB (eliminate cold-start rebuild)
- Automated evaluation harness against ground-truth facts
- Multi-AMC expansion
- API versioning for potential third-party integrations

---

*Case study written by MAYA + Sentinel + Forge — 2026-06-05*
