# Checkpoint

Date: 2026-06-06
Bug: Backend ignored scheme_name

Root Cause:
ChatRequest only accepted message.
scheme_name was silently discarded.

Fix:
Added Optional[str] scheme_name
Enriched retrieval query before retrieval

Verification:
15/15 retrieval tests passed

Verified:
2026-06-06T21:26 — all 5 tabs tested in production
AUM, exit load, expense ratio, fund manager — all returning answers with Groww citations
Defence tab confirmed working last

Deployed:
2026-06-06T15:43Z — commit fb854af live on Railway
Ingestion: 5 schemes, 51 chunks, 9/9 sections per scheme
Groq: confirmed succeeding in production logs
scheme resolution: hdfc-mid-cap, hdfc-small-cap confirmed resolving in live logs

Known:
AUM query triggers grounding_failure in validator — link-only fallback returned
Pre-existing validator behaviour, not related to this fix
→ Fixed in Bug-002 below

---

# Bug-002

Date: 2026-06-07
Bug: AUM query returns "unable to generate" on all 5 schemes

Root Cause:
Groww chunks store total assets as ₹2,70,046 Cr (abbreviation).
LLM naturally expands Cr → crore in its answer.
Validator's literal substring check: "2,70,046 crore" not in chunk text.
Grounding failure triggered → link-only fallback every time.

Fix:
Normalise chunk text before comparison only.
re.sub(r"\bCr\b", "crore", all_chunk_text) inside check_grounding().
Answer text, corpus, retrieval, generation — untouched.

Verification:
4/4 tests passed
  ✅ AUM query — previously failing, now grounded
  ✅ Expense ratio — unchanged behaviour
  ✅ Fund manager — unchanged behaviour
  ✅ Hallucination — fake ₹1,23,456.99 crore still caught

File changed: app/validator.py only
Lines changed: 2 operational, 6 comments/docstring

Pending:
Commit and push approval
Railway redeploy

---

## Diff — Bug-002

```diff
diff --git a/app/validator.py b/app/validator.py
index 5ccf225..ac35fbf 100644
--- a/app/validator.py
+++ b/app/validator.py
@@ -99,12 +99,21 @@ def check_advisory(text: str) -> list[str]:
 
 
 def check_grounding(answer: str, chunks: list[dict]) -> list[str]:
-    """Return numbers found in answer but absent from all chunk texts."""
+    """Return numbers found in answer but absent from all chunk texts.
+
+    Chunk text is normalised before comparison to handle the unit alias
+    'Cr' (abbreviation used by Groww) vs 'crore' (expanded form used by
+    the LLM).  Only the comparison string is modified — answer text,
+    chunk data, and all outputs are untouched.
+    """
     all_chunk_text = " ".join(c.get("text", "") for c in chunks)
+    # Normalise unit alias: 'Cr' (Groww abbreviation) → 'crore' (LLM output form).
+    # Applied to chunk text only, inside this function, for comparison purposes.
+    chunk_text_normalised = re.sub(r"\bCr\b", "crore", all_chunk_text)
     ungrounded = []
     for num in _NUMBER_RE.findall(answer):
         num_clean = num.strip()
-        if num_clean and num_clean not in all_chunk_text:
+        if num_clean and num_clean not in chunk_text_normalised:
             ungrounded.append(num_clean)
     return ungrounded
```

---

## Diff

```diff
diff --git a/app/main.py b/app/main.py
index 601b19e..1d63f9b 100644
--- a/app/main.py
+++ b/app/main.py
@@ -24,6 +24,7 @@ import os
 import re
 import time
 from contextlib import asynccontextmanager
+from typing import Optional
 
 from fastapi import FastAPI, Request
 from fastapi.middleware.cors import CORSMiddleware
@@ -145,6 +146,7 @@ app.add_middleware(
 
 class ChatRequest(BaseModel):
     message: str
+    scheme_name: Optional[str] = None
 
 
 class ChatResponse(BaseModel):
@@ -200,7 +202,10 @@ async def chat(request: Request):
         return JSONResponse(content=_make_refusal(query_class))
 
     # 4. Factual path: retrieve → generate → format
-    retrieval_result = retrieve(message)
+    # Enrich the retrieval query with scheme context when the frontend sends it.
+    # The original message is kept clean for the LLM prompt (generate step).
+    retrieval_query = f"{message} for {body.scheme_name}" if body.scheme_name else message
+    retrieval_result = retrieve(retrieval_query)
     generation_result = generate(message, retrieval_result)
     response_body = format_response(generation_result)
```
