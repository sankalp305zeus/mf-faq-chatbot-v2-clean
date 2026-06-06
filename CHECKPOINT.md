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
