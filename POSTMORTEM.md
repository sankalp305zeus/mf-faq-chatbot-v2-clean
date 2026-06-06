# MF FAQ Assistant — Project Postmortem

**Project:** mf-faq-chatbot-v2-clean
**Period:** 2026-06-04 to 2026-06-07
**Status:** MVP shipped and production-verified

---

## Bug-001 — scheme_name silently dropped by backend

### What happened
The Lovable frontend sent `{ "message": "Who is the fund manager?", "scheme_name": "Large Cap" }` on every request. The backend's `ChatRequest` Pydantic model only declared `message: str`. Pydantic silently discarded `scheme_name`. The retriever received a bare question with no scheme context, scored 0.0 against all 5 scheme slugs, and fired `_unresolved_refusal()` on every short query.

### Symptoms
- All contextless queries ("Who is the fund manager?", "What is the AUM?") returned: "I can only answer questions about these HDFC schemes… Please specify which scheme."
- Scheme tab selected in UI had no effect on backend behaviour.
- Full-name queries ("What is the expense ratio of HDFC Mid Cap?") worked fine.

### Detection
Sentinel investigation: traced full request payload from Lovable source code (`ChatApp.tsx:82`). Found `scheme_name` present in frontend payload. Confirmed absent in `ChatRequest` model (`main.py:146`). Confirmed Pydantic drops extra fields by default.

### Root cause
API contract mismatch. Frontend built with scheme-tab context in mind. Backend schema written for natural-language full-name queries only. No integration test existed across the boundary.

### Fix
Three lines in `app/main.py` (commit `fb854af`):
1. `from typing import Optional`
2. `scheme_name: Optional[str] = None` added to `ChatRequest`
3. `retrieval_query = f"{message} for {body.scheme_name}" if body.scheme_name else message`

### What would have prevented it
- An integration test sending a short query with `scheme_name` and asserting `is_refusal=False`.
- A contract test validating that all fields the frontend sends are accepted by the backend schema.
- API contract review during frontend handoff — before the first deploy.

---

## Bug-002 — AUM grounding failure (Cr vs crore)

### What happened
Groww stores total AMC assets as `₹2,70,046 Cr` (abbreviation). The LLM naturally expands `Cr` to `crore` in its answer. The grounding validator performed a literal substring match: `"2,70,046 crore"` not in chunk text (which has `"2,70,046 Cr"`). Grounding failure triggered → link-only fallback on every AUM query across all 5 schemes.

### Symptoms
- "What is the AUM?" returned "I'm unable to generate a response right now. Please visit the scheme page for complete details." on every scheme.
- All other queries (expense ratio, exit load, fund manager, benchmark) worked correctly.
- Deploy log: `grounding_failure: ['2,70,046 crore']`

### Detection
Quantified corpus: scanned all 51 chunks for unit variants. Found 5 `Cr` occurrences (fund_house section, one per scheme) vs 10 `crore` occurrences. Reproduced exact failure by simulating LLM answer with `Cr`→`crore` expansion against actual retrieved chunks.

### Root cause
The grounding validator was designed for exact string matching. The source data (Groww HTML) uses `Cr` as an abbreviation in one specific data field. LLMs consistently expand abbreviations. The mismatch was deterministic and reproducible across all schemes.

### Fix
One operational line in `app/validator.py:check_grounding()` (commit `d6c066f`):
```python
chunk_text_normalised = re.sub(r"\bCr\b", "crore", all_chunk_text)
```
Applied to chunk text only, inside the comparison function. Answer text, corpus, retrieval, generation — untouched.

### What would have prevented it
- Unit alias test in the validator test suite: assert `"2,70,046 crore"` passes grounding when chunk contains `"₹2,70,046 Cr"`.
- Corpus audit during ingestion: flag any unit abbreviation that differs from LLM output convention.
- Grounding validator design principle: normalise before compare, not after.

---

## Lessons Learned

| Lesson | Application |
|---|---|
| Test the API boundary, not just each side independently | Add integration tests that send realistic frontend payloads end-to-end |
| LLMs expand abbreviations — build for it | Normalise unit aliases in corpus at ingestion time or in validator |
| Pydantic silently drops extra fields — this is a footgun | Explicit `model_config = ConfigDict(extra='forbid')` surfaces this at runtime |
| Short queries are the dominant UX pattern for a tabbed UI | Design retrieval with UI context in mind from the start |
| Grounding validation is strict by design — needs corpus-aware normalisation | Audit source data for abbreviations before writing validator patterns |
