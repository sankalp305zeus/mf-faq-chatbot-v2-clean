"""Phase 4 — constrained Groq answer generation.

Receives a RetrievalResult from Phase 3 and returns a GenerationResult.

Decision tree:
  1. scheme_resolved=False  → immediate refusal (no LLM call)
  2. MOCK_LLM=True          → deterministic stub built from top chunk text
  3. Groq call succeeds     → answer validated → return GenerationResult
  4. Groq call fails        → link-only fallback GenerationResult
  5. Validator flags advisory language → advisory refusal GenerationResult
  6. Validator flags grounding failure → link-only fallback GenerationResult

Public API:
    from app.generator import generate, GenerationResult

    result = generate(query="...", retrieval_result=...)
    # result.answer, result.citation_url, result.last_updated, result.is_refusal

Standalone smoke test:
    MOCK_LLM=1 python -m app.generator
    GROQ_API_KEY=gsk_... python -m app.generator   # live Groq
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.retriever import RetrievalResult
from app.validator import validate, ValidationResult
from ingestion.config import load_corpus

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────
# Kept as a module constant so it is easy to audit and diff.

SYSTEM_PROMPT = (
    "You are a facts-only mutual fund FAQ assistant for HDFC schemes.\n\n"
    "Rules you must follow without exception:\n"
    "1. Answer ONLY using facts that are explicitly present in the CONTEXT provided. "
    "Do not use outside knowledge.\n"
    "2. Your answer must be at most 3 sentences.\n"
    "3. Do not provide investment advice, buy/sell/hold recommendations, "
    "fund comparisons, or return/performance predictions.\n"
    "4. Do not include any URL in your answer — citations are added separately.\n"
    "5. If the context does not contain enough information to answer, respond with exactly: "
    "\"I don't have that specific information. "
    "Please visit the scheme page for complete details.\"\n"
    "6. Do not mention any fund, AMC, or financial product not present in the context."
)

# ── Data contract ──────────────────────────────────────────────────────────────

@dataclass
class GenerationResult:
    """Output of the generation layer.  Consumed by Phase 5 formatter."""
    answer: str
    citation_url: str
    last_updated: str
    is_refusal: bool
    refusal_reason: Optional[str] = None
    validation_issues: list[str] = field(default_factory=list)


# ── Corpus helpers ─────────────────────────────────────────────────────────────

_corpus_cache: Optional[dict] = None


def _get_corpus() -> dict:
    global _corpus_cache
    if _corpus_cache is None:
        _corpus_cache = load_corpus()
    return _corpus_cache


def _refusal_url() -> str:
    return _get_corpus().get("refusal_links", {}).get(
        "amfi",
        "https://www.amfiindia.com/investor-corner/investor-center/about-mf.html",
    )


# ── Context assembly ───────────────────────────────────────────────────────────

def _build_context(chunks: list[dict]) -> str:
    parts = []
    for chunk in chunks:
        section = chunk.get("section", "general")
        text = chunk.get("text", "").strip()
        parts.append(f"[Section: {section}]\n{text}")
    return "\n\n".join(parts)


def _build_user_message(query: str, context: str, scheme_name: str, source_url: str) -> str:
    return (
        f"CONTEXT for {scheme_name}:\n"
        f"Source: {source_url}\n\n"
        f"{context}\n\n"
        f"QUESTION: {query}"
    )


# ── Groq call (lazy import so ingestion works without groq installed) ──────────

def _call_groq(messages: list[dict]) -> str:
    from groq import Groq  # noqa: PLC0415 — intentional lazy import

    client = Groq(api_key=settings.require_groq())
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0,       # deterministic for a facts-only system
        max_tokens=256,      # 3 sentences is well under 256 tokens
    )
    return response.choices[0].message.content.strip()


# ── Fallback builders ──────────────────────────────────────────────────────────

def _mock_answer(retrieval_result: RetrievalResult) -> str:
    """Deterministic stub for MOCK_LLM=1.  Returns top chunk text verbatim."""
    if not retrieval_result.chunks:
        return (
            "I don't have that specific information. "
            "Please visit the scheme page for complete details."
        )
    return retrieval_result.chunks[0]["text"]


def _unresolved_refusal(retrieval_result: RetrievalResult) -> GenerationResult:
    names = retrieval_result.supported_schemes
    if names:
        scheme_list = "; ".join(names)
        answer = (
            f"I can only answer questions about these HDFC schemes: {scheme_list}. "
            "Please specify which scheme you are asking about."
        )
    else:
        answer = (
            "I can only answer factual questions about HDFC schemes in my corpus. "
            "Please specify a scheme name."
        )
    return GenerationResult(
        answer=answer,
        citation_url=_refusal_url(),
        last_updated="",
        is_refusal=True,
        refusal_reason="scheme_not_resolved",
    )


def _advisory_refusal() -> GenerationResult:
    return GenerationResult(
        answer=(
            "I can only answer factual questions about mutual fund scheme details "
            "such as expense ratio, exit load, or fund manager information. "
            "For investment guidance, please consult a SEBI-registered financial advisor."
        ),
        citation_url=_refusal_url(),
        last_updated="",
        is_refusal=True,
        refusal_reason="advisory_language_in_output",
    )


def _link_only_fallback(retrieval_result: RetrievalResult) -> GenerationResult:
    last_updated = (
        retrieval_result.chunks[0]["last_updated"] if retrieval_result.chunks else ""
    )
    return GenerationResult(
        answer=(
            "I'm unable to generate a response right now. "
            "Please visit the scheme page for complete details."
        ),
        citation_url=retrieval_result.source_url or _refusal_url(),
        last_updated=last_updated,
        is_refusal=False,
        refusal_reason="llm_unavailable_or_grounding_failure",
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def generate(
    query: str,
    retrieval_result: RetrievalResult,
) -> GenerationResult:
    """Generate a grounded, validated answer from a RetrievalResult.

    Always returns a GenerationResult — never raises.
    """
    # Path 1: scheme not resolved → immediate refusal
    if not retrieval_result.scheme_resolved:
        logger.info("generate: scheme_resolved=False — returning unresolved refusal")
        return _unresolved_refusal(retrieval_result)

    source_url = retrieval_result.source_url or ""
    last_updated = (
        retrieval_result.chunks[0]["last_updated"] if retrieval_result.chunks else ""
    )

    # Path 2: mock LLM
    if settings.mock_llm:
        logger.info("generate: MOCK_LLM=True — returning stub answer")
        raw = _mock_answer(retrieval_result)
        vr: ValidationResult = validate(raw, source_url, retrieval_result)
        if vr.is_refusal:
            return _advisory_refusal()
        if any("grounding_failure" in i for i in vr.issues):
            return _link_only_fallback(retrieval_result)
        return GenerationResult(
            answer=vr.answer,
            citation_url=vr.citation_url,
            last_updated=last_updated,
            is_refusal=False,
            validation_issues=vr.issues,
        )

    # Path 3: real Groq call
    context = _build_context(retrieval_result.chunks)
    user_msg = _build_user_message(
        query, context,
        retrieval_result.scheme_name or "",
        source_url,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    try:
        raw = _call_groq(messages)
        logger.info("generate: Groq succeeded (%d chars)", len(raw))
    except Exception as exc:
        logger.warning("generate: Groq failed (%s) — link-only fallback", exc)
        return _link_only_fallback(retrieval_result)

    # Path 4: validate
    vr = validate(raw, source_url, retrieval_result)
    if vr.issues:
        logger.info("generate: validation issues — %s", vr.issues)

    if vr.is_refusal:
        return _advisory_refusal()

    if any("grounding_failure" in i for i in vr.issues):
        logger.warning("generate: grounding failure — returning link-only fallback")
        return _link_only_fallback(retrieval_result)

    return GenerationResult(
        answer=vr.answer,
        citation_url=vr.citation_url,
        last_updated=last_updated,
        is_refusal=False,
        validation_issues=vr.issues,
    )


# ── Smoke test ─────────────────────────────────────────────────────────────────

_SMOKE_CASES: list[tuple[str, bool]] = [
    # (query, expect_refusal)
    ("What is the expense ratio of HDFC Mid Cap fund?",          False),
    ("Who manages the HDFC Small Cap Fund?",                     False),
    ("Exit load for HDFC Defence Fund",                          False),
    ("Minimum SIP for HDFC Gold ETF fund of fund",               False),
    ("What is the benchmark for HDFC Large Cap?",                False),
    ("Tax on HDFC Mid Cap redemption after 1 year",              False),
    ("What is the weather in Mumbai?",                           True),   # unresolved
]


def _run_smoke() -> int:
    print("=== Phase 4 generation smoke test ===\n")
    mode = "MOCK_LLM" if settings.mock_llm else "LIVE_GROQ"
    if not settings.mock_llm and not settings.groq_api_key:
        print("GROQ_API_KEY not set and MOCK_LLM=0. Set MOCK_LLM=1 or provide GROQ_API_KEY.")
        return 1

    print(f"Mode: {mode}  Model: {settings.groq_model}\n")
    errors = 0

    from app.retriever import retrieve  # local import — only needed for smoke test
    for query, expect_refusal in _SMOKE_CASES:
        r = retrieve(query)
        result = generate(query, r)
        ok = result.is_refusal == expect_refusal
        status = "OK" if ok else "FAIL"
        if not ok:
            errors += 1
        print(f"[{status}] {query!r}")
        print(f"       is_refusal={result.is_refusal}  "
              f"refusal_reason={result.refusal_reason}")
        print(f"       citation_url={result.citation_url}")
        if result.validation_issues:
            print(f"       issues={result.validation_issues}")
        print(f"       answer: {result.answer[:120]}{'…' if len(result.answer) > 120 else ''}")
        print()

    total = len(_SMOKE_CASES)
    print(f"Smoke test complete. {total - errors}/{total} passed.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_smoke())
