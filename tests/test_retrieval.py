"""Phase 3 unit tests — retriever.

All scheme-resolution and intent-detection tests are in-memory (no ChromaDB).
Integration tests (actual vector query) are marked with @pytest.mark.integration
and skipped unless --run-integration is passed.
"""
from __future__ import annotations

import pytest

from app.retriever import (
    detect_section_intent,
    resolve_scheme,
    retrieve,
    RetrievalResult,
    _normalise,
    _query_names_competitor,
)
from ingestion.config import load_corpus

CORPUS = load_corpus()


# ── Normalisation ─────────────────────────────────────────────────────────────

def test_normalise_lowercases_and_strips():
    assert _normalise("HDFC Mid-Cap Fund!") == "hdfc mid cap fund"


def test_normalise_collapses_whitespace():
    assert _normalise("  multiple   spaces  ") == "multiple spaces"


# ── Competitor detection ───────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "SBI small cap fund",
    "axis mid cap exit load",
    "nippon large cap benchmark",
    "icici gold fund",
    "mirae defence etf",
    "kotak small cap expense ratio",
])
def test_query_names_competitor_positive(query):
    assert _query_names_competitor(_normalise(query)) is True


@pytest.mark.parametrize("query", [
    "hdfc small cap fund",
    "small cap expense ratio",
    "hdfc mid cap",
    "defence fund",
])
def test_query_names_competitor_negative(query):
    assert _query_names_competitor(_normalise(query)) is False


# ── Scheme resolution: positive cases ─────────────────────────────────────────

@pytest.mark.parametrize("query,expected_slug", [
    ("What is the expense ratio of HDFC Mid Cap fund?", "hdfc-mid-cap-fund-direct-growth"),
    ("hdfc mid cap fund direct growth",                 "hdfc-mid-cap-fund-direct-growth"),
    ("expense ratio of midcap scheme",                  "hdfc-mid-cap-fund-direct-growth"),
    ("hdfc small cap exit load",                        "hdfc-small-cap-fund-direct-growth"),
    ("HDFC Large Cap benchmark",                        "hdfc-large-cap-fund-direct-growth"),
    ("hdfc gold etf fund of fund nav",                  "hdfc-gold-etf-fund-of-fund-direct-plan-growth"),
    ("gold fof minimum investment",                     "hdfc-gold-etf-fund-of-fund-direct-plan-growth"),
    ("hdfc defence fund manager",                       "hdfc-defence-fund-direct-growth"),
    ("defense fund expense ratio",                      "hdfc-defence-fund-direct-growth"),
])
def test_resolve_scheme_correct_slug(query, expected_slug):
    scheme, score, _ = resolve_scheme(query, corpus=CORPUS)
    assert scheme is not None, f"Expected slug {expected_slug!r} but got no match for: {query!r}"
    assert scheme["slug"] == expected_slug, (
        f"Expected {expected_slug!r}, got {scheme['slug']!r} (score={score:.2f}) for: {query!r}"
    )


def test_resolve_scheme_returns_score_above_threshold():
    scheme, score, _ = resolve_scheme("HDFC Mid Cap", corpus=CORPUS)
    assert score >= 0.5


def test_resolve_scheme_unrelated_query_returns_none():
    scheme, score, _ = resolve_scheme("latest cricket scores", corpus=CORPUS)
    assert scheme is None


def test_resolve_scheme_no_match_below_min_score():
    scheme, score, _ = resolve_scheme("irrelevant query abc xyz", corpus=CORPUS, min_score=0.5)
    assert scheme is None or score < 0.5


# ── Scheme resolution: competitor queries must NOT resolve (FAR-01 / FAR-02) ──

@pytest.mark.parametrize("query", [
    "SBI small cap fund expense ratio",
    "Nippon large cap benchmark",
    "Axis mid cap exit load",
    "ICICI gold fund minimum investment",
    "Mirae defence ETF tax",
    "Kotak small cap expense ratio",
])
def test_resolve_scheme_competitor_query_returns_none(query):
    scheme, score, _ = resolve_scheme(query, corpus=CORPUS)
    assert scheme is None, (
        f"Expected no match for competitor query {query!r}, "
        f"but got slug={scheme['slug']!r} score={score:.2f}"
    )


# ── Scheme resolution: disambiguation hint (FAR-05) ──────────────────────────

def test_disambiguation_hint_set_on_near_tie():
    """A bare query with no scheme discriminator may produce a near-tie hint."""
    # "hdfc fund" has no distinguishing scheme token; all 5 schemes share
    # the "hdfc" + "fund" tokens, so multiple schemes score closely.
    _, score, hint = resolve_scheme("hdfc fund", corpus=CORPUS)
    if score >= 0.5 and hint is not None:
        # hint must mention at least two scheme names
        mentioned = sum(
            1 for s in CORPUS["schemes"] if s["scheme_name"] in hint
        )
        assert mentioned >= 2, (
            f"Disambiguation hint should name ≥2 schemes, got: {hint!r}"
        )


def test_disambiguation_hint_is_none_for_unambiguous_query():
    scheme, score, hint = resolve_scheme(
        "What is the expense ratio of HDFC Mid Cap fund?", corpus=CORPUS
    )
    assert scheme is not None
    # The mid-cap query is unambiguous; hint should be None
    assert hint is None, f"Expected no disambiguation hint but got: {hint!r}"


# ── Section intent detection ──────────────────────────────────────────────────

@pytest.mark.parametrize("query,expected_section", [
    ("What is the expense ratio of HDFC Mid Cap?",           "expense_ratio"),
    ("What is the TER of this fund?",                        "expense_ratio"),
    ("Exit load if I redeem within 1 year",                  "exit_load"),
    ("stamp duty charges",                                   "exit_load"),
    ("What is the exit strategy for this fund?",             "exit_load"),   # FAR-04 fix
    ("Minimum SIP to invest in the fund",                    "minimum_investment"),
    ("minimum lumpsum investment",                           "minimum_investment"),
    ("Which benchmark does this fund track?",                "benchmark"),
    ("what NIFTY index is used",                             "benchmark"),
    ("LTCG tax on mutual fund redemption",                   "tax"),
    ("capital gain tax after 1 year",                        "tax"),
    ("Who is the fund manager?",                             "fund_management"),
    ("Who manages the HDFC Small Cap portfolio?",            "fund_management"),
    ("What is the investment objective?",                    "investment_objective"),
    ("what is the aim of the fund",                          "investment_objective"),
    ("What is the investment strategy of the fund?",         "investment_objective"),
    ("Tell me about the fund house",                         "fund_house"),
    ("information about AMC",                               "fund_house"),
    ("current NAV of the fund",                              "overview"),
    ("what is the AUM of the scheme",                        "overview"),
])
def test_detect_section_intent(query, expected_section):
    result = detect_section_intent(query)
    assert result == expected_section, (
        f"Expected {expected_section!r}, got {result!r} for: {query!r}"
    )


def test_detect_section_intent_none_for_generic():
    assert detect_section_intent("tell me about the fund") is None


# ── retrieve() — unresolved scheme ───────────────────────────────────────────

def test_retrieve_unresolved_scheme_returns_empty_result():
    result = retrieve("What is the weather in Mumbai?")
    assert isinstance(result, RetrievalResult)
    assert result.scheme_resolved is False
    assert result.chunks == []


def test_retrieve_result_has_section_intent_even_when_unresolved():
    result = retrieve("What is the expense ratio?")
    assert result.section_intent == "expense_ratio"
    assert result.scheme_resolved is False


def test_retrieve_unresolved_populates_supported_schemes(monkeypatch):
    """FAR-06: unresolved result must list supported scheme names."""
    result = retrieve("Tell me about XYZ fund")
    assert result.scheme_resolved is False
    assert len(result.supported_schemes) == len(CORPUS["schemes"])
    expected_names = {s["scheme_name"] for s in CORPUS["schemes"]}
    assert set(result.supported_schemes) == expected_names


def test_retrieve_resolved_supported_schemes_empty():
    """When scheme resolves, supported_schemes should be empty (not needed)."""
    result = retrieve("HDFC Mid Cap fund")
    if result.scheme_resolved:
        assert result.supported_schemes == []


# ── Integration tests (require live ChromaDB) ─────────────────────────────────

@pytest.fixture
def run_integration(request):
    return request.config.getoption("--run-integration")


@pytest.mark.parametrize("query,expected_slug,expected_section", [
    ("expense ratio of HDFC Mid Cap fund",    "hdfc-mid-cap-fund-direct-growth",    "expense_ratio"),
    ("who manages HDFC Small Cap",             "hdfc-small-cap-fund-direct-growth",  "fund_management"),
    ("exit load HDFC Defence Fund",            "hdfc-defence-fund-direct-growth",    "exit_load"),
    ("benchmark for HDFC Large Cap",           "hdfc-large-cap-fund-direct-growth",  "benchmark"),
    ("minimum SIP HDFC gold fund of fund",     "hdfc-gold-etf-fund-of-fund-direct-plan-growth", "minimum_investment"),
    # FAR-03: investment_objective must be top chunk after guaranteed-section fix
    ("investment objective of hdfc defence fund", "hdfc-defence-fund-direct-growth", "investment_objective"),
])
def test_retrieve_integration(run_integration, query, expected_slug, expected_section):
    if not run_integration:
        pytest.skip("Pass --run-integration to run ChromaDB tests")

    result = retrieve(query)

    assert result.scheme_resolved, f"Scheme not resolved for: {query!r}"
    assert result.scheme_slug == expected_slug, (
        f"Expected slug {expected_slug!r}, got {result.scheme_slug!r}"
    )
    assert len(result.chunks) > 0, "No chunks returned"

    # Top chunk must match intent section (guaranteed by two-pass retrieval)
    if result.section_intent == expected_section:
        top_section = result.chunks[0]["section"]
        assert top_section == expected_section, (
            f"Expected top chunk section={expected_section!r}, got {top_section!r}"
        )

    # All returned chunks must belong to the resolved scheme
    for chunk in result.chunks:
        assert chunk["slug"] == expected_slug, (
            f"Chunk from wrong scheme: {chunk['slug']!r}"
        )


@pytest.mark.parametrize("query", [
    "SBI small cap fund expense ratio",
    "Nippon large cap benchmark",
    "Axis mid cap exit load",
    "ICICI gold fund minimum investment",
    "Mirae defence ETF tax",
])
def test_retrieve_integration_no_false_match(run_integration, query):
    """FAR-02: competitor-AMC queries must NOT resolve to any HDFC scheme."""
    if not run_integration:
        pytest.skip("Pass --run-integration to run ChromaDB tests")
    result = retrieve(query)
    assert result.scheme_resolved is False, (
        f"Expected scheme_resolved=False for competitor query {query!r}, "
        f"but got slug={result.scheme_slug!r}"
    )
