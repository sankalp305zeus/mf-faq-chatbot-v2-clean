"""Tests for app/classifier.py — query intent classification.

Covers all 5 query classes + edge cases including advisory-sounding factual queries.
"""
import pytest

from app.classifier import (
    classify,
    FACTUAL,
    ADVISORY,
    COMPARISON,
    PERFORMANCE,
    OUT_OF_SCOPE,
)


# ── Factual queries — must NOT be blocked ─────────────────────────────────────

@pytest.mark.parametrize("query", [
    "What is the expense ratio of HDFC Mid Cap?",
    "Who manages the HDFC Small Cap Fund?",
    "Exit load for HDFC Defence Fund",
    "Minimum SIP for HDFC Gold ETF fund of fund",
    "What is the benchmark for HDFC Large Cap?",
    "Tell me about the investment objective of HDFC Defence Fund",
    "What is the ISIN of HDFC Mid Cap?",
    "What is the AUM of HDFC Large Cap?",
    "What is the fund house behind HDFC Mid Cap?",
    "What are the tax implications of HDFC Small Cap after 1 year?",
    "What section of the fund is the exit load?",           # "exit load" is factual
    "What fees apply to HDFC Gold Fund redemption?",        # "fees" ≠ "advice"
])
def test_factual_queries(query):
    assert classify(query) == FACTUAL, f"Expected FACTUAL for: {query!r}"


# ── Advisory queries — must be blocked ────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "Should I invest in HDFC Mid Cap?",
    "Is HDFC Defence Fund a good investment?",
    "Do you recommend HDFC Small Cap?",
    "Is it worth investing in HDFC Gold Fund?",
    "Can I buy HDFC Large Cap right now?",
    "Please advise me on HDFC Mid Cap Fund",
    "Any suggestions for HDFC schemes?",
    "Is it safe to invest in mid cap right now?",
])
def test_advisory_queries(query):
    assert classify(query) == ADVISORY, f"Expected ADVISORY for: {query!r}"


# ── Comparison queries — must be blocked ──────────────────────────────────────

@pytest.mark.parametrize("query", [
    "HDFC Mid Cap vs HDFC Small Cap",
    "Which is better — Mid Cap or Large Cap?",
    "Compare HDFC Mid Cap and Defence Fund",
    "What is the difference between HDFC Mid Cap and Large Cap?",
    "Which HDFC fund should I pick?",
    "HDFC Small Cap versus Gold Fund",
])
def test_comparison_queries(query):
    assert classify(query) == COMPARISON, f"Expected COMPARISON for: {query!r}"


# ── Performance queries — must be blocked ─────────────────────────────────────

@pytest.mark.parametrize("query", [
    "What is the 3 year return of HDFC Mid Cap?",
    "CAGR of HDFC Small Cap",
    "How has HDFC Defence Fund performed?",
    "How much profit will I get from HDFC Gold Fund?",
    "Historical performance of HDFC Large Cap",
    "Expected returns from HDFC Mid Cap SIP",
])
def test_performance_queries(query):
    assert classify(query) == PERFORMANCE, f"Expected PERFORMANCE for: {query!r}"


# ── Out-of-scope queries ───────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "",
    "   ",
    "hi",
    "ok",
    "yes",
])
def test_out_of_scope_queries(query):
    assert classify(query) == OUT_OF_SCOPE, f"Expected OUT_OF_SCOPE for: {query!r}"


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_never_raises_on_empty():
    assert classify("") == OUT_OF_SCOPE


def test_never_raises_on_whitespace():
    assert classify("   ") == OUT_OF_SCOPE


def test_comparison_beats_advisory():
    """'Which is better' is COMPARISON not ADVISORY (comparison checked first)."""
    assert classify("Which is better for me to invest in?") == COMPARISON


def test_factual_with_number_not_performance():
    """A number in a factual query (e.g. minimum investment) must not trip performance."""
    result = classify("What is the minimum SIP amount for HDFC Gold Fund?")
    assert result == FACTUAL


def test_case_insensitivity():
    """Classifier must work on any casing."""
    assert classify("SHOULD I INVEST IN HDFC MID CAP?") == ADVISORY
    assert classify("what is the EXPENSE RATIO of hdfc mid cap?") == FACTUAL
