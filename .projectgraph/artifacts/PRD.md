# PRD — Mutual Fund FAQ Assistant

Owner: Maya (discover) · Mode: ai-rag · Date: 2026-06-04

## Problem
Retail investors comparing schemes, and support/content teams handling repetitive queries, need quick, verifiable mutual fund facts. Generic assistants give unsourced or advisory answers, creating compliance risk.

## Goal
A facts-only, source-backed RAG assistant over a fixed 5-page HDFC corpus that answers objective queries and refuses anything advisory.

## Target users
- Retail investors comparing mutual fund schemes
- Customer support / content teams handling repetitive MF queries

## In scope (factual query types)
- Expense ratio, exit load, minimum SIP / minimum investment
- ELSS lock-in (where applicable), riskometer classification, benchmark index
- Fund management: manager name, tenure, experience, education, other schemes
- Investment objective, fund house details
- Statement / capital-gains download *guidance* (link-only)

## Out of scope (must refuse)
- Advice: "Should I invest?", "Is this good?"
- Comparison: "Which is better?", "Mid cap vs large cap"
- Performance / returns calculation or projection (link to scheme page only)
- Schemes not in the 5-URL corpus; unrelated topics

## Corpus (active, fixed)
| Scheme | URL |
|--------|-----|
| HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| HDFC Large Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| HDFC Gold ETF Fund of Fund Direct Plan Growth | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| HDFC Defence Fund Direct Growth | https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth |

## Response contract
- Body ≤ 3 sentences
- Exactly 1 `citation_url` from the allowlist (AMFI/SEBI for refusals)
- Footer: `Last updated from sources: <date>` (from chunk metadata, never model-inferred)
- JSON: `{ answer, citation_url, last_updated, is_refusal }`

## UI requirements (minimal)
- Welcome message + visible disclaimer: "Facts-only. No investment advice."
- 3 clickable example questions (incl. one fund-management question)
- Free-text input; renders answer + citation + footer
- Never prompts for or accepts PII

## Compliance / privacy
- Stateless; no accounts, no identity-linked history/analytics
- Reject/strip PII patterns (PAN, Aadhaar, account #, OTP, email, phone) before LLM
- Allowlisted citations; no training on user data; basic per-IP rate limiting

## Success criteria
- Accurate factual retrieval with valid citations
- Strict facts-only adherence; correct refusal of advisory queries
- Clean minimal UI; p95 end-to-end < 5 s

## Deliverables
- README (setup, AMC/schemes, RAG architecture, known limitations)
- Disclaimer snippet
- deployment-plan.md and a deployed demo
