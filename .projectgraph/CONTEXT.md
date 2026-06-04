# Context

## Identity
- Name: Mutual Fund FAQ Assistant
- Slug: mf-faq-chatbot
- One-liner: Facts-only RAG chatbot answering verifiable HDFC mutual fund questions with one citation each
- Type: product
- Stage: prototype
- Mode: ai-rag

## Problem
Retail investors and support teams need quick, verifiable facts about specific mutual fund schemes, but public sources are scattered and generic chatbots give unsourced advice.

## Solution
A small-corpus RAG assistant over 5 HDFC Groww scheme pages. Answers factual queries in ≤3 sentences with one citation. Refuses advisory/comparison/performance queries. No PII, no recommendations.

## Constraints
- Official/reference sources only (5 Groww HDFC URLs); no blogs/aggregators
- Never collect or store PII (PAN, Aadhaar, account #, OTP, email, phone)
- No advice, comparisons, or return calculations
- Every factual answer: ≤3 sentences + exactly 1 citation + "Last updated" footer

## Rules
- Free embeddings (BGE) + local vector store; LLM via Groq
- Citations must be in the 5-URL allowlist (or AMFI/SEBI for refusals)
- Ingestion runs offline daily (10:00 AM IST); never on the request path
- Output validator gates every response before it reaches the user

## Assumptions (unvalidated)
- Groww scheme pages expose all 9 target sections in scrapable HTML
- ~50–150 chunks total is sufficient retrieval coverage for 5 schemes
