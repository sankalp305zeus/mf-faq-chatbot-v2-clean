"""Phase 5 — response formatter.

Converts a GenerationResult into the JSON response contract:
    {answer, citation_url, last_updated, is_refusal}

Appends "Last updated: YYYY-MM-DD" footer to factual answers.
Footer is suppressed when last_updated is empty (refusals, unresolved schemes).

Public API:
    from app.formatter import format_response

    response_dict = format_response(generation_result)
"""
from __future__ import annotations

from app.generator import GenerationResult


def format_response(result: GenerationResult) -> dict:
    """Build the JSON-serialisable response dict from a GenerationResult.

    The 'answer' field includes the footer when last_updated is non-empty
    and the result is not a refusal.
    """
    answer = result.answer.strip()

    if result.last_updated and not result.is_refusal:
        answer = f"{answer}\n\nLast updated: {result.last_updated}"

    return {
        "answer": answer,
        "citation_url": result.citation_url,
        "last_updated": result.last_updated,
        "is_refusal": result.is_refusal,
    }
