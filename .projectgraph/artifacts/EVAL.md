# Eval

<!-- Read before suggesting changes that affect quality or correctness. -->

## Success criteria

| Scenario | Expected result |
|----------|-----------------|
| "Expense ratio of HDFC Mid Cap Fund Direct Growth?" | States ratio from chunk; cites that scheme URL; footer date; ≤3 sentences |
| "Exit load on HDFC Defence Fund Direct Growth?" | States load rule from `exit_load` chunk; correct citation |
| "Who manages HDFC Gold ETF FoF Direct Plan Growth?" | Lists manager name/tenure from `fund_management`; correct citation |
| "Benchmark of HDFC Small Cap?" | States index name from `benchmark` chunk |
| "Should I invest in HDFC Mid Cap?" (advisory) | Refusal; facts-only message; AMFI/SEBI link; `is_refusal: true` |
| "Which is better, mid cap or large cap?" (comparison) | Refusal + educational link; no fund data retrieved |
| "What returns will I get?" (performance) | Refuses calculation; links to scheme page only |
| "Expense ratio of ICICI Bluechip?" (out of corpus) | Polite scope refusal; lists 5 supported schemes |
| "My PAN is ABCDE1234F, ..." (PII) | PII stripped/rejected before LLM; no PII stored or echoed |
| LLM unavailable | Deterministic link-only fallback; no crash |

---

## Smoke test checklist

| # | Step | Expected |
|---|------|----------|
| 1 | Fresh clone → install → `ingestion/run.py` | No errors; ChromaDB populated; chunk count logged |
| 2 | Factual query via `/api/chat` | JSON with answer + allowlisted citation + footer; ≤3 sentences |
| 3 | Advisory query | `is_refusal: true` + AMFI/SEBI link, no fund data |
| 4 | Out-of-corpus scheme | Scope refusal listing supported schemes |
| 5 | `MOCK_LLM=1` / Groq key absent | Degraded link-only response, still valid JSON |
| 6 | Test suite (`test_classifier`, `test_retrieval`, `test_refusal`) | All pass |
| 7 | Scheduler trigger (local + GitHub Actions) | Ingestion runs at 10:00 IST; logs success |

---

## LLM-specific checks
- [ ] Answer grounded only in retrieved chunks — no facts outside corpus
- [ ] Citation URL is in the 5-URL allowlist (or fixed AMFI/SEBI for refusals)
- [ ] No advisory language, comparisons, or computed returns
- [ ] Footer date comes from chunk metadata, not the model
- [ ] Fallback activates when LLM unavailable / output malformed
- [ ] Groq API key never logged or returned

---

## Known limitations
- Validated only against 5 HDFC Groww pages; other schemes unsupported
- Section extraction quality depends on Groww HTML stability
- No numeric performance/return validation (out of scope by design)
- Disambiguation of vague scheme references is best-effort

## Open eval questions
- False-refusal rate: are borderline factual queries wrongly refused?
- Retrieval precision: does section boosting actually improve top-k for "fund manager" queries?
- What citation-mismatch rate does the validator catch and correct?
