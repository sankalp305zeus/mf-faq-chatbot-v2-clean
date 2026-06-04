"""Phase 1 unit tests — structured section extractor.

Tests are purely in-memory: they build a minimal mfServerSideData dict and
assert on section output.  No filesystem, no network, no HTML parsing.
"""
from __future__ import annotations

import pytest

from ingestion.config import SECTION_TAGS
from ingestion.sections import MissingRequiredField, coverage, extract_sections


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _minimal_mf(**overrides) -> dict:
    """Smallest valid mfServerSideData that satisfies all required fields."""
    base = {
        "scheme_name": "Test Fund Direct Growth",
        "expense_ratio": 0.73,
        "exit_load": "Exit load of 1% if redeemed within 1 year.",
        "min_sip_investment": 100,
        "min_investment_amount": 100,
        "mini_additional_investment": 100,
        "aum": 94744.72,
        "nav": 219.077,
        "nav_date": "03-Jun-2026",
        "benchmark_name": "NIFTY Midcap 150 Total Return Index",
        "benchmark": "NIFTY Midcap 150 TRI",
        "fund_manager": "Chirag Setalvad",
        "fund_manager_details": [
            {
                "person_name": "Chirag Setalvad",
                "date_from": "2012-12-31T18:30:00.000Z",
                "education": "B.Sc and MBA from University of North Carolina.",
                "experience": "Prior to joining HDFC AMC he worked at HDFC.",
            }
        ],
        "description": "The scheme seeks long-term capital appreciation.",
        "fund_house": "HDFC Mutual Fund",
        "launch_date": "01-Jan-2013",
        "registrar_agent": "CAMS",
        "category": "Equity",
        "sub_category": "Mid Cap",
        "plan_type": "Direct",
        "scheme_type": "Growth",
        "stamp_duty": "0.005% (from July 1st, 2020)",
        "isin": "INF179K01XQ0",
        "nfo_risk": "Very High",
        "return_stats": [{"risk": "Very High", "risk_rating": 6}],
        "lock_in": {"years": None, "months": None, "days": None},
        "category_info": {
            "tax_impact": (
                "If you redeem within one year, returns are taxed at 20%. "
                "If you redeem after one year, returns exceeding Rs 1.25 lakh are taxed at 12.5%."
            )
        },
        "amc_info": {
            "name": "HDFC Mutual Fund",
            "aum": 937047.59,
            "description": "HDFC Mutual Fund started operations on 30/06/2000.",
        },
        "historic_fund_expense": [],
    }
    base.update(overrides)
    return base


# ── Shape tests ───────────────────────────────────────────────────────────────

def test_all_nine_section_keys_present():
    out = extract_sections(_minimal_mf())
    assert set(out.keys()) == set(SECTION_TAGS)
    assert all(isinstance(v, list) for v in out.values())


def test_all_sections_populated_with_valid_mf():
    out = extract_sections(_minimal_mf())
    empty = [tag for tag, blocks in out.items() if not blocks]
    assert not empty, f"Expected all sections non-empty; empty: {empty}"


# ── Content correctness ───────────────────────────────────────────────────────

def test_expense_ratio_contains_value():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["expense_ratio"])
    assert "0.73%" in combined


def test_exit_load_contains_rule():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["exit_load"])
    assert "1%" in combined
    assert "1 year" in combined


def test_minimum_investment_sip_and_lumpsum():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["minimum_investment"])
    assert "₹100" in combined            # SIP amount
    assert "lumpsum" in combined.lower() # lumpsum mention


def test_no_lock_in_stated_when_null():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["minimum_investment"]).lower()
    assert "no mandatory lock-in" in combined


def test_lock_in_stated_when_present():
    mf = _minimal_mf(lock_in={"years": 3, "months": None, "days": None})
    out = extract_sections(mf)
    combined = " ".join(out["minimum_investment"]).lower()
    assert "lock-in" in combined and "3 year" in combined


def test_benchmark_contains_index_name():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["benchmark"])
    assert "NIFTY Midcap 150 Total Return Index" in combined


def test_tax_from_category_info():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["tax"])
    assert "20%" in combined or "12.5%" in combined


def test_fund_management_one_block_per_manager():
    mf = _minimal_mf(fund_manager_details=[
        {"person_name": "Alice", "date_from": "2020-01-01T00:00:00.000Z",
         "education": "MBA.", "experience": "10 years."},
        {"person_name": "Bob", "date_from": "2022-06-01T00:00:00.000Z",
         "education": "CA.", "experience": "5 years."},
    ])
    out = extract_sections(mf)
    assert len(out["fund_management"]) == 2
    assert "Alice" in out["fund_management"][0]
    assert "Bob" in out["fund_management"][1]
    # Each bio intact in a single string
    assert "MBA." in out["fund_management"][0]


def test_investment_objective_is_description():
    out = extract_sections(_minimal_mf())
    assert "long-term capital appreciation" in out["investment_objective"][0]


def test_fund_house_mentions_amc():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["fund_house"])
    assert "HDFC Mutual Fund" in combined


def test_overview_nav_and_risk():
    out = extract_sections(_minimal_mf())
    combined = " ".join(out["overview"])
    assert "219.077" in combined
    assert "Very High" in combined


# ── Validation / failure tests ────────────────────────────────────────────────

def test_raises_on_missing_expense_ratio():
    mf = _minimal_mf()
    del mf["expense_ratio"]
    with pytest.raises(MissingRequiredField, match="expense_ratio"):
        extract_sections(mf)


def test_raises_on_missing_fund_manager_details():
    mf = _minimal_mf(fund_manager_details=[])
    with pytest.raises(MissingRequiredField):
        extract_sections(mf)


def test_raises_on_missing_benchmark():
    mf = _minimal_mf()
    del mf["benchmark_name"]
    with pytest.raises(MissingRequiredField, match="benchmark_name"):
        extract_sections(mf)


def test_raises_on_missing_min_sip():
    mf = _minimal_mf()
    del mf["min_sip_investment"]
    with pytest.raises(MissingRequiredField, match="min_sip_investment"):
        extract_sections(mf)


# ── Coverage helper ───────────────────────────────────────────────────────────

def test_coverage_returns_block_counts():
    out = extract_sections(_minimal_mf())
    cov = coverage(out)
    assert set(cov.keys()) == set(SECTION_TAGS)
    assert all(isinstance(v, int) for v in cov.values())
    assert cov["expense_ratio"] >= 1
