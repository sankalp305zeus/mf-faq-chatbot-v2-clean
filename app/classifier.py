"""Phase 5 — query intent classifier.

Labels an incoming query as one of:
  factual      — verifiable question about scheme details (expense ratio, exit load, fund manager…)
  advisory     — investment advice request (should I invest, is this good…)
  comparison   — asking to compare funds or pick the best
  performance  — asking about returns, CAGR, past performance, profit
  out_of_scope — empty, gibberish, or too short to interpret

Rules-first: keyword regex covers ~95% of cases without an LLM call.
Priority order: comparison > advisory > performance > factual.
(Comparison checked before advisory so "which is better" doesn't misfire on advisory.)

Public API:
    from app.classifier import classify, FACTUAL, ADVISORY, COMPARISON, PERFORMANCE, OUT_OF_SCOPE

    label = classify("What is the expense ratio of HDFC Mid Cap?")
    # → "factual"
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Class constants ────────────────────────────────────────────────────────────

FACTUAL = "factual"
ADVISORY = "advisory"
COMPARISON = "comparison"
PERFORMANCE = "performance"
OUT_OF_SCOPE = "out_of_scope"

QueryClass = str  # one of the five constants above

# ── Rule sets (matched against lowercased query) ───────────────────────────────

_COMPARISON_PATTERNS: list[str] = [
    r"\bbetter than\b",
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bwhich is better\b",
    r"\bdifference between\b",
    r"\bwhich (?:\w+ )?fund\b",
    r"\bwhich one should\b",
    r"\bbest fund\b",
    r"\bbest among\b",
    r"\brank(?:ing)?\b",
]

_ADVISORY_PATTERNS: list[str] = [
    r"\bshould i\b",
    r"\bshould i invest\b",
    r"\bis it (?:good|safe|worth|right)\b",
    r"\bis (?:this|the) (?:fund )?(?:good|safe|worth|right)\b",
    r"\badvice\b",
    r"\badvise\b",
    r"\brecommend\b",
    r"\bsuggestions?\b",
    r"\bworth investing\b",
    r"\bgood (?:investment|option|choice)\b",
    r"\bi should\b",
    r"\bshould buy\b",
    r"\bshould sell\b",
    r"\bcan i (?:invest|buy|sell)\b",
]

_PERFORMANCE_PATTERNS: list[str] = [
    r"\breturn[s]?\b",
    r"\bcagr\b",
    r"\bperform(?:ance|ed|ing|s)?\b",
    r"\bhow much (?:will|would|can|has|have|did)\b",
    r"\bprofit\b",
    r"\bgain[s]?\b",
    r"\bbeat\b",
    r"\boutperform\b",
    r"\bhistorical\b",
    r"\bpast performance\b",
    r"\b\d+\s*(?:year|yr)\s*return\b",
    r"\bgrowth rate\b",
    r"\bsip (?:calculator|returns?)\b",
    r"\bexpected return\b",
    r"\bhow much (?:money|profit)\b",
]

# ── Matcher ────────────────────────────────────────────────────────────────────

def _match_any(patterns: list[str], text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in patterns)


# ── Public API ─────────────────────────────────────────────────────────────────

def classify(query: str) -> QueryClass:
    """Return one of: factual, advisory, comparison, performance, out_of_scope.

    Never raises. Safe to call with any string including empty.
    """
    stripped = query.strip()

    if len(stripped) < 4:
        logger.debug("classify: out_of_scope (too short) — %r", stripped)
        return OUT_OF_SCOPE

    if _match_any(_COMPARISON_PATTERNS, stripped):
        logger.debug("classify: comparison — %r", stripped[:80])
        return COMPARISON

    if _match_any(_ADVISORY_PATTERNS, stripped):
        logger.debug("classify: advisory — %r", stripped[:80])
        return ADVISORY

    if _match_any(_PERFORMANCE_PATTERNS, stripped):
        logger.debug("classify: performance — %r", stripped[:80])
        return PERFORMANCE

    logger.debug("classify: factual — %r", stripped[:80])
    return FACTUAL
