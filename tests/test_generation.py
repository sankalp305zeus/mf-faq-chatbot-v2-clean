"""Phase 4 unit + integration tests — generator and validator.

Unit tests: in-memory, no ChromaDB, no Groq.
Integration tests: require --run-integration (live ChromaDB + MOCK_LLM=1 or real Groq).
"""
from __future__ import annotations

import pytest

from app.generator import (
    GenerationResult,
    _advisory_refusal,
    _link_only_fallback,
    _unresolved_refusal,
    generate,
)
from app.retriever import RetrievalResult
from app.validator import (
    ValidationResult,
    check_advisory,
    check_citation,
    check_grounding,
    split_sentences,
    truncate_to_n_sentences,
    validate,
)
from ingestion.config import load_corpus

CORPUS = load_corpus()
_VALID_URL = CORPUS["schemes"][0]["source_url"]   # always in allowlist
_AMFI_URL  = CORPUS["refusal_links"]["amfi"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_result(
    scheme_resolved: bool = True,
    slug: str = "hdfc-mid-cap-fund-direct-growth",
    source_url: str = _VALID_URL,
    chunks: list[dict] | None = None,
    supported_schemes: list[str] | None = None,
) -> RetrievalResult:
    if chunks is None:
        chunks = [
            {
                "id": f"{slug}#expense_ratio#0",
                "text": "The expense ratio of HDFC Mid Cap Fund Direct Growth is 0.73%.",
                "source_url": source_url,
                "scheme_name": "HDFC Mid Cap Fund Direct Growth",
                "section": "expense_ratio",
                "slug": slug,
                "last_updated": "2026-06-04",
                "score": 0.95,
            }
        ]
    return RetrievalResult(
        query="test query",
        scheme_resolved=scheme_resolved,
        scheme_slug=slug if scheme_resolved else None,
        scheme_name="HDFC Mid Cap Fund Direct Growth" if scheme_resolved else None,
        source_url=source_url if scheme_resolved else None,
        section_intent="expense_ratio",
        chunks=chunks,
        supported_schemes=supported_schemes or [],
    )


# ── Sentence splitting ────────────────────────────────────────────────────────

def test_split_two_sentences():
    text = "The expense ratio is 0.73%. This is as of the last ingestion date."
    assert len(split_sentences(text)) == 2


def test_split_three_sentences():
    text = "The fund was launched in 2007. It is managed by Chirag Setalvad. The AUM is large."
    assert len(split_sentences(text)) == 3


def test_split_single_sentence():
    assert len(split_sentences("The exit load is 1%.")) == 1


def test_truncate_no_change_when_under():
    text = "Sentence one. Sentence two."
    assert truncate_to_n_sentences(text, 3) == text.strip()


def test_truncate_cuts_to_three():
    text = "One. Two. Three. Four. Five."
    result = truncate_to_n_sentences(text, 3)
    assert len(split_sentences(result)) == 3
    assert "Four" not in result
    assert "Five" not in result


def test_truncate_adds_period_if_missing():
    text = "One. Two. Three! Four"
    result = truncate_to_n_sentences(text, 3)
    assert result.endswith((".", "!", "?"))


# ── Advisory language detection ───────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "You should invest in this fund.",
    "I recommend this scheme.",
    "This is a better option for you.",
    "This fund is guaranteed to perform well.",
    "You can expect high returns from this fund.",
    "I would consider investing here.",
    "This fund will grow significantly.",
])
def test_check_advisory_detects_advisory_text(text):
    assert check_advisory(text), f"Expected advisory hit for: {text!r}"


@pytest.mark.parametrize("text", [
    "The expense ratio is 0.73%.",
    "The exit load is 1% if redeemed within 1 year.",
    "The benchmark index is NIFTY Midcap 150 TRI.",
    "Chirag Setalvad has been managing the fund since June 2007.",
    "The minimum SIP investment is ₹100.",
])
def test_check_advisory_clean_text(text):
    assert not check_advisory(text), f"Expected no advisory hit for: {text!r}"


# ── Grounding check ───────────────────────────────────────────────────────────

def test_grounding_passes_when_numbers_in_chunks():
    chunks = [{"text": "The expense ratio is 0.73%."}]
    assert check_grounding("The expense ratio is 0.73%.", chunks) == []


def test_grounding_fails_when_number_not_in_chunks():
    chunks = [{"text": "The expense ratio is 0.73%."}]
    ungrounded = check_grounding("The expense ratio is 1.50%.", chunks)
    assert "1.50%" in ungrounded or any("1.50" in u for u in ungrounded)


def test_grounding_passes_when_no_numbers_in_answer():
    chunks = [{"text": "The fund invests in mid cap stocks."}]
    assert check_grounding("The fund invests in mid cap stocks.", chunks) == []


def test_grounding_multiple_numbers_all_found():
    chunks = [{"text": "Min SIP is ₹100. Expense ratio is 0.73%."}]
    answer = "The minimum SIP is ₹100 and expense ratio is 0.73%."
    assert check_grounding(answer, chunks) == []


def test_grounding_one_of_two_numbers_missing():
    chunks = [{"text": "Min SIP is ₹100."}]
    answer = "The minimum SIP is ₹100 and expense ratio is 0.73%."
    ungrounded = check_grounding(answer, chunks)
    # 0.73% is not in the chunk
    assert any("0.73" in u for u in ungrounded)


# ── Citation check ────────────────────────────────────────────────────────────

def test_citation_valid_corpus_url():
    assert check_citation(_VALID_URL) is True


def test_citation_amfi_url():
    assert check_citation(_AMFI_URL) is True


def test_citation_random_url_invalid():
    assert check_citation("https://example.com/fake") is False


# ── validate() ───────────────────────────────────────────────────────────────

def test_validate_clean_answer_no_issues():
    rr = _make_result()
    vr = validate("The expense ratio is 0.73%.", _VALID_URL, rr)
    assert not vr.is_refusal
    assert vr.citation_url == _VALID_URL
    assert vr.issues == []


def test_validate_truncates_long_answer():
    rr = _make_result()
    text = "One fact. Two facts. Three facts. Four facts."
    vr = validate(text, _VALID_URL, rr)
    assert len(split_sentences(vr.answer)) == 3
    assert any("sentence_count" in i for i in vr.issues)


def test_validate_flags_advisory_as_refusal():
    rr = _make_result()
    vr = validate("You should invest in this fund.", _VALID_URL, rr)
    assert vr.is_refusal is True
    assert any("advisory_language" in i for i in vr.issues)


def test_validate_replaces_off_allowlist_citation():
    rr = _make_result()
    vr = validate("The expense ratio is 0.73%.", "https://random.com", rr)
    assert vr.citation_url == _VALID_URL
    assert any("citation_not_in_allowlist" in i for i in vr.issues)


def test_validate_grounding_failure_recorded():
    rr = _make_result()
    # chunk has 0.73%, answer claims 1.50%
    vr = validate("The expense ratio is 1.50%.", _VALID_URL, rr)
    assert any("grounding_failure" in i for i in vr.issues)
    assert not vr.is_refusal  # grounding failure ≠ advisory refusal


# ── generate() — unit (no ChromaDB, MOCK_LLM paths) ──────────────────────────

def test_generate_unresolved_scheme_returns_refusal(monkeypatch):
    rr = _make_result(
        scheme_resolved=False,
        supported_schemes=["HDFC Mid Cap Fund Direct Growth", "HDFC Large Cap Fund Direct Growth"],
    )
    result = generate("random query", rr)
    assert result.is_refusal is True
    assert result.refusal_reason == "scheme_not_resolved"
    assert "HDFC Mid Cap" in result.answer
    assert result.citation_url == _AMFI_URL


def test_generate_unresolved_includes_all_supported_schemes(monkeypatch):
    supported = [s["scheme_name"] for s in CORPUS["schemes"]]
    rr = _make_result(scheme_resolved=False, supported_schemes=supported)
    result = generate("unknown fund query", rr)
    for name in supported:
        assert name in result.answer


def test_generate_mock_llm_returns_grounded_answer(monkeypatch):
    monkeypatch.setattr("app.generator.settings.mock_llm", True)
    rr = _make_result()
    result = generate("What is the expense ratio?", rr)
    assert not result.is_refusal
    assert "0.73%" in result.answer
    assert result.citation_url == _VALID_URL
    assert result.last_updated == "2026-06-04"


def test_generate_mock_llm_advisory_chunk_triggers_refusal(monkeypatch):
    monkeypatch.setattr("app.generator.settings.mock_llm", True)
    advisory_chunk = {
        "id": "x#overview#0",
        "text": "You should invest in this fund for high returns.",
        "source_url": _VALID_URL,
        "scheme_name": "HDFC Mid Cap Fund Direct Growth",
        "section": "overview",
        "slug": "hdfc-mid-cap-fund-direct-growth",
        "last_updated": "2026-06-04",
        "score": 0.9,
    }
    rr = _make_result(chunks=[advisory_chunk])
    result = generate("tell me about the fund", rr)
    assert result.is_refusal is True
    assert result.refusal_reason == "advisory_language_in_output"


def test_generate_groq_failure_returns_link_only_fallback(monkeypatch):
    def _fail(_):
        raise RuntimeError("Groq timeout")

    monkeypatch.setattr("app.generator._call_groq", _fail)
    monkeypatch.setattr("app.generator.settings.mock_llm", False)
    monkeypatch.setattr("app.generator.settings.groq_api_key", "fake-key")

    rr = _make_result()
    result = generate("What is the expense ratio?", rr)
    assert not result.is_refusal
    assert result.refusal_reason == "llm_unavailable_or_grounding_failure"
    assert result.citation_url == _VALID_URL


def test_generate_result_has_all_required_fields(monkeypatch):
    monkeypatch.setattr("app.generator.settings.mock_llm", True)
    rr = _make_result()
    result = generate("expense ratio?", rr)
    assert hasattr(result, "answer")
    assert hasattr(result, "citation_url")
    assert hasattr(result, "last_updated")
    assert hasattr(result, "is_refusal")


# ── Integration tests (live ChromaDB + MOCK_LLM or real Groq) ─────────────────

@pytest.fixture
def run_integration(request):
    return request.config.getoption("--run-integration")


@pytest.mark.parametrize("query,expected_section", [
    ("What is the expense ratio of HDFC Mid Cap fund?",  "expense_ratio"),
    ("Who manages the HDFC Small Cap Fund?",             "fund_management"),
    ("Exit load for HDFC Defence Fund",                  "exit_load"),
    ("Minimum SIP for HDFC Gold ETF fund of fund",       "minimum_investment"),
    ("Benchmark for HDFC Large Cap",                     "benchmark"),
])
def test_generate_integration_mock(run_integration, query, expected_section, monkeypatch):
    """Full retrieval → generation pipeline with MOCK_LLM=1."""
    if not run_integration:
        pytest.skip("Pass --run-integration to run pipeline tests")

    monkeypatch.setattr("app.generator.settings.mock_llm", True)

    from app.retriever import retrieve
    rr = retrieve(query)
    result = generate(query, rr)

    assert not result.is_refusal, f"Unexpected refusal for: {query!r}"
    assert result.answer, "Empty answer"
    assert result.citation_url in {s["source_url"] for s in CORPUS["schemes"]}
    assert result.last_updated  # non-empty date string


def test_generate_integration_unresolved(run_integration):
    """Out-of-corpus query must produce a refusal with supported scheme names."""
    if not run_integration:
        pytest.skip("Pass --run-integration to run pipeline tests")

    from app.retriever import retrieve
    rr = retrieve("What is the weather in Mumbai?")
    result = generate("What is the weather in Mumbai?", rr)

    assert result.is_refusal is True
    assert result.refusal_reason == "scheme_not_resolved"
    supported = [s["scheme_name"] for s in CORPUS["schemes"]]
    for name in supported:
        assert name in result.answer


@pytest.mark.parametrize("query", [
    "expense ratio of HDFC Mid Cap fund",
    "who manages HDFC Small Cap",
    "exit load HDFC Defence Fund",
])
def test_generate_integration_live_groq(run_integration, query):
    """Live Groq call — skipped unless --run-integration AND GROQ_API_KEY set."""
    if not run_integration:
        pytest.skip("Pass --run-integration to run live Groq tests")

    from app.config import settings as s
    if not s.groq_api_key:
        pytest.skip("GROQ_API_KEY not set — skipping live Groq test")

    from app.retriever import retrieve
    rr = retrieve(query)
    result = generate(query, rr)

    assert result.answer
    assert result.citation_url
    # Answer must be ≤ 3 sentences
    from app.validator import split_sentences
    assert len(split_sentences(result.answer)) <= 3
