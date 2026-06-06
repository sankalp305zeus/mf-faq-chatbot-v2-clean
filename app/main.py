"""Phase 5 — FastAPI application.

Single endpoint: POST /api/chat
  Body:     {"message": "string"}
  Response: {"answer": str, "citation_url": str, "last_updated": str, "is_refusal": bool}

Request pipeline:
  1. PII guard  — reject before any processing; no PII reaches retrieval or LLM
  2. Classify   — factual / advisory / comparison / performance / out_of_scope
  3. Route      — non-factual → immediate refusal (AMFI/SEBI link, no retrieval)
  4. Factual    — retrieve → generate → validate → format → JSON

Startup: BGE model + ChromaDB warmup via retriever.warmup() (resolves FAR-07).
Rate limiting: per-IP via slowapi; limit from RATE_LIMIT env var.
Structured logging: query_class, scheme_slug, is_refusal, latency_ms — never PII.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.classifier import classify, FACTUAL
from app.config import settings
from app.formatter import format_response
from app.generator import generate
from app.retriever import retrieve, warmup

logger = logging.getLogger(__name__)

# ── Rate limiter ───────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

# ── PII patterns ───────────────────────────────────────────────────────────────
# Checked against raw user input before any processing.
# Conservative set: PAN, Aadhaar, Indian mobile, email.
# Avoids broad digit patterns that produce false positives on fund data.

_PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                              # PAN: ABCDE1234F
    re.compile(r"\b[2-9][0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b"),               # Aadhaar: 12 digits
    re.compile(r"(?<!\d)(?:\+91[\s\-]?)?[6-9][0-9]{9}(?!\d)"),            # Indian mobile (10 digits)
    re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"), # Email
]


def _contains_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII_PATTERNS)


# ── Static refusal copy ────────────────────────────────────────────────────────

_AMFI_URL = "https://www.amfiindia.com/investor-corner/investor-center/about-mf.html"

_REFUSAL_COPY: dict[str, str] = {
    "advisory": (
        "I can only answer factual questions about mutual fund scheme details. "
        "For investment guidance, please consult a SEBI-registered financial advisor."
    ),
    "comparison": (
        "I cannot compare funds or recommend one over another. "
        "I can answer factual questions about individual HDFC schemes such as "
        "expense ratio, exit load, or fund manager details."
    ),
    "performance": (
        "I cannot provide return or performance data. "
        "I can answer factual questions about scheme details like expense ratio, "
        "exit load, benchmark, or minimum investment."
    ),
    "out_of_scope": (
        "I can only answer factual questions about HDFC mutual fund schemes. "
        "Try asking about expense ratio, exit load, fund manager, or minimum investment."
    ),
    "pii": (
        "Your message appears to contain personal information such as a PAN, "
        "Aadhaar number, phone number, or email address. "
        "Please do not share personal details — "
        "I can only answer factual questions about HDFC mutual fund schemes."
    ),
}


def _make_refusal(key: str) -> dict:
    return {
        "answer": _REFUSAL_COPY[key],
        "citation_url": _AMFI_URL,
        "last_updated": "",
        "is_refusal": True,
    }


# ── Lifespan: warmup (FAR-07) ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: warming up BGE model and ChromaDB…")
    try:
        warmup()
        logger.info("startup: warmup complete — first request will not incur cold-start penalty")
    except Exception as exc:
        logger.warning("startup: warmup failed (%s) — first request may be slow", exc)
    yield


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="MF FAQ Assistant", version="0.5.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — origins are configurable via ALLOWED_ORIGINS env var so production
# deployments can be locked to the specific frontend URL.
# ALLOWED_ORIGINS="*"  → wildcard (local dev default)
# ALLOWED_ORIGINS="https://foo.up.railway.app,https://bar.example.com"  → explicit list
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_allow_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins.strip() != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request / response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    scheme_name: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    citation_url: str
    last_updated: str
    is_refusal: bool


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit(settings.rate_limit)
async def chat(request: Request):
    t0 = time.perf_counter()

    # Parse and validate the JSON body manually (slowapi decorator conflicts with
    # FastAPI Pydantic body injection when both request: Request and BaseModel are present).
    try:
        raw = await request.json()
        body = ChatRequest(**raw)
    except (ValueError, ValidationError, Exception):
        return JSONResponse(
            status_code=422,
            content={"detail": "Request body must be JSON with a 'message' string field."},
        )

    message = body.message.strip()

    # 1. PII guard — reject before anything else; never log the raw message
    if _contains_pii(message):
        logger.info(
            "chat: pii_detected is_refusal=True latency_ms=%.0f",
            (time.perf_counter() - t0) * 1000,
        )
        return JSONResponse(content=_make_refusal("pii"))

    # 2. Classify
    query_class = classify(message)

    # 3. Non-factual → immediate refusal (no retrieval, no LLM)
    if query_class != FACTUAL:
        logger.info(
            "chat: query_class=%s is_refusal=True latency_ms=%.0f",
            query_class,
            (time.perf_counter() - t0) * 1000,
        )
        return JSONResponse(content=_make_refusal(query_class))

    # 4. Factual path: retrieve → generate → format
    # Enrich the retrieval query with scheme context when the frontend sends it.
    # The original message is kept clean for the LLM prompt (generate step).
    retrieval_query = f"{message} for {body.scheme_name}" if body.scheme_name else message
    retrieval_result = retrieve(retrieval_query)
    generation_result = generate(message, retrieval_result)
    response_body = format_response(generation_result)

    # Additive UI metadata for "Why this answer?" panel — never breaks existing contract
    response_body["scheme_name"] = retrieval_result.scheme_name
    response_body["section_intent"] = retrieval_result.section_intent

    logger.info(
        "chat: query_class=%s scheme=%s is_refusal=%s latency_ms=%.0f",
        query_class,
        retrieval_result.scheme_slug or "unresolved",
        generation_result.is_refusal,
        (time.perf_counter() - t0) * 1000,
    )

    return JSONResponse(content=response_body)
