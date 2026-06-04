"""Phase 4 — post-generation output validator.

Checks a generated answer for four properties in this order:
  1. Sentence count ≤ 3  (truncates silently)
  2. Advisory language   (forces is_refusal=True)
  3. Numeric grounding   (flags ungrounded numbers; caller decides fallback)
  4. Citation allowlist  (replaces off-list URL with scheme source_url)

Public API:
    from app.validator import validate, ValidationResult

    vr = validate(answer, citation_url, retrieval_result)
    # vr.answer        — possibly truncated
    # vr.citation_url  — possibly corrected
    # vr.is_refusal    — True if advisory language detected
    # vr.issues        — list of strings for logging
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.retriever import RetrievalResult
from ingestion.config import load_corpus

# ── Advisory language patterns ─────────────────────────────────────────────────
# Matched against the lowercased generated text.
_ADVISORY_PATTERNS: list[str] = [
    r"\bshould invest\b",
    r"\bi recommend\b",
    r"\brecommend(?:ed|ation)?\b",
    r"\bbetter (?:fund|option|choice)\b",
    r"\bgood investment\b",
    r"\boutperform\b",
    r"\bbest (?:fund|option|choice)\b",
    r"\byou should\b",
    r"\bi would\b",
    r"\bconsider investing\b",
    r"\bwill (?:grow|increase|rise)\b",
    r"\bexpected? returns?\b",
    r"\bguaranteed?\b",
    r"\bhigh returns?\b",
]

# ── Numeric grounding regex ────────────────────────────────────────────────────
# Matches numbers that carry factual weight: percentages, rupee amounts, years.
_NUMBER_RE = re.compile(
    r"\b\d+(?:[.,]\d+)*\s*(?:%|₹|crore|lakh|rs\.?|inr)?\b",
    re.IGNORECASE,
)

_corpus_cache: Optional[dict] = None


def _get_allowlist() -> set[str]:
    global _corpus_cache
    if _corpus_cache is None:
        _corpus_cache = load_corpus()
    allowed: set[str] = {s["source_url"] for s in _corpus_cache["schemes"]}
    allowed.update(_corpus_cache.get("refusal_links", {}).values())
    return allowed


# ── Data contract ──────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    answer: str
    citation_url: str
    is_refusal: bool = False
    issues: list[str] = field(default_factory=list)


# ── Sentence utilities ─────────────────────────────────────────────────────────

def split_sentences(text: str) -> list[str]:
    """Split text into sentences at .!? followed by whitespace + capital letter."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def truncate_to_n_sentences(text: str, n: int = 3) -> str:
    sentences = split_sentences(text)
    if len(sentences) <= n:
        return text.strip()
    truncated = " ".join(sentences[:n])
    if truncated and truncated[-1] not in ".!?":
        truncated += "."
    return truncated


# ── Individual checks (exported for testing) ──────────────────────────────────

def check_advisory(text: str) -> list[str]:
    """Return list of matched advisory patterns (empty = clean)."""
    lower = text.lower()
    return [p for p in _ADVISORY_PATTERNS if re.search(p, lower)]


def check_grounding(answer: str, chunks: list[dict]) -> list[str]:
    """Return numbers found in answer but absent from all chunk texts."""
    all_chunk_text = " ".join(c.get("text", "") for c in chunks)
    ungrounded = []
    for num in _NUMBER_RE.findall(answer):
        num_clean = num.strip()
        if num_clean and num_clean not in all_chunk_text:
            ungrounded.append(num_clean)
    return ungrounded


def check_citation(url: str) -> bool:
    """Return True if url is in the corpus + refusal allowlist."""
    return url in _get_allowlist()


# ── Public entry point ─────────────────────────────────────────────────────────

def validate(
    answer: str,
    citation_url: str,
    retrieval_result: RetrievalResult,
) -> ValidationResult:
    """Validate and repair a generated answer where safe to do so.

    Sentence truncation is a silent repair.
    Advisory language forces is_refusal=True (caller must substitute refusal copy).
    Grounding failure is recorded in issues; caller decides whether to fallback.
    Off-allowlist citation is replaced with the scheme's canonical source_url.
    """
    issues: list[str] = []
    is_refusal = False

    # 1. Sentence count
    sentences = split_sentences(answer)
    if len(sentences) > 3:
        answer = truncate_to_n_sentences(answer, 3)
        issues.append(f"sentence_count: truncated from {len(sentences)} to 3")

    # 2. Advisory language
    advisory_hits = check_advisory(answer)
    if advisory_hits:
        is_refusal = True
        issues.append(f"advisory_language: {advisory_hits}")

    # 3. Numeric grounding
    ungrounded = check_grounding(answer, retrieval_result.chunks)
    if ungrounded:
        issues.append(f"grounding_failure: {ungrounded}")

    # 4. Citation allowlist
    if not check_citation(citation_url):
        replacement = retrieval_result.source_url or next(iter(_get_allowlist()))
        issues.append(f"citation_not_in_allowlist: replaced {citation_url!r} → {replacement!r}")
        citation_url = replacement

    return ValidationResult(
        answer=answer,
        citation_url=citation_url,
        is_refusal=is_refusal,
        issues=issues,
    )
