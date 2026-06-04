"""Phase 1 — structured section extractor.

Reads the mfServerSideData dict from Groww's __NEXT_DATA__ SSR payload and
assembles the 9 canonical section dicts defined in ARCHITECTURE.md.

Each section is a list of human-readable strings — complete factual sentences
ready to embed.  Every string is self-contained: a reader (or LLM) needs no
other context to answer the question that string addresses.

Validation
----------
extract_sections() raises MissingRequiredField if any field marked
required=True is absent or None in the payload.  This implements the
value-presence gate recommended by the Sentinel review.

Public API
----------
  extract_sections(mf: dict) -> dict[str, list[str]]
  coverage(sections)         -> dict[str, int]
  MissingRequiredField       -- raised on validation failure
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ingestion.config import SECTION_TAGS


class MissingRequiredField(ValueError):
    pass


# Fields that MUST be present and non-None for a parse to be considered valid.
# Keyed by the mfServerSideData key; value is the section it primarily feeds.
REQUIRED_FIELDS: dict[str, str] = {
    "expense_ratio":       "expense_ratio",
    "exit_load":           "exit_load",
    "min_sip_investment":  "minimum_investment",
    "benchmark_name":      "benchmark",
    "fund_manager_details":"fund_management",
    "description":         "investment_objective",
}


def _val(mf: dict, key: str, required: bool = False) -> Any:
    v = mf.get(key)
    if required and (v is None or v == "" or v == []):
        raise MissingRequiredField(
            f"Required field '{key}' is missing or empty in mfServerSideData"
        )
    return v


def _date(iso: str | None) -> str:
    """ISO datetime → 'DD-Mon-YYYY' for human-readable strings."""
    if not iso:
        return "unknown date"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        return iso[:10]


def _crore(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"₹{value:,.2f} crore"


# ── Section builders ──────────────────────────────────────────────────────────

def _expense_ratio(mf: dict) -> list[str]:
    er = _val(mf, "expense_ratio", required=True)
    scheme = mf.get("scheme_name", "This scheme")
    blocks = [
        f"The expense ratio of {scheme} is {er}% (as of the last ingestion date).",
    ]
    # Historic expense shows recent changes — useful context.
    history = mf.get("historic_fund_expense", [])
    if history:
        latest = max(history, key=lambda x: x.get("as_on_date", ""))
        hist_er = latest.get("expense_ratio")
        hist_date = latest.get("as_on_date", "")[:10]
        if hist_er is not None and str(hist_er) != str(er):
            blocks.append(
                f"Historically, the expense ratio was {hist_er}% as of {hist_date}."
            )
    return blocks


def _exit_load(mf: dict) -> list[str]:
    el = _val(mf, "exit_load", required=True)
    scheme = mf.get("scheme_name", "This scheme")
    blocks = [f"Exit load for {scheme}: {el}"]
    stamp = mf.get("stamp_duty")
    if stamp:
        blocks.append(f"Stamp duty: {stamp}.")
    return blocks


def _minimum_investment(mf: dict) -> list[str]:
    min_sip = _val(mf, "min_sip_investment", required=True)
    min_lump = mf.get("min_investment_amount", min_sip)
    mini_add = mf.get("mini_additional_investment")
    scheme = mf.get("scheme_name", "This scheme")
    blocks = [
        f"The minimum SIP investment for {scheme} is ₹{min_sip}.",
        f"The minimum lumpsum (first purchase) investment is ₹{min_lump}.",
    ]
    if mini_add and str(mini_add) != str(min_lump):
        blocks.append(f"The minimum additional purchase amount is ₹{mini_add}.")
    # Lock-in (relevant for ELSS; null for others)
    lock = mf.get("lock_in") or {}
    years = lock.get("years")
    months = lock.get("months")
    if years:
        blocks.append(f"This scheme has a lock-in period of {years} year(s).")
    elif months:
        blocks.append(f"This scheme has a lock-in period of {months} month(s).")
    else:
        blocks.append("This scheme has no mandatory lock-in period.")
    return blocks


def _benchmark(mf: dict) -> list[str]:
    name = _val(mf, "benchmark_name", required=True)
    short = mf.get("benchmark", name)
    scheme = mf.get("scheme_name", "This scheme")
    blocks = [f"The benchmark index for {scheme} is {name} ({short})."]
    return blocks


def _tax(mf: dict) -> list[str]:
    cat_info = mf.get("category_info") or {}
    tax_text = cat_info.get("tax_impact")
    if tax_text:
        return [tax_text.strip()]
    # Fallback: derive from category
    category = (mf.get("category") or "").lower()
    if "equity" in category:
        return [
            "For equity funds: STCG (held < 1 year) is taxed at 20%; "
            "LTCG (held ≥ 1 year) exceeding ₹1.25 lakh per year is taxed at 12.5%."
        ]
    if "debt" in category:
        return [
            "For debt funds: gains are added to income and taxed at slab rate "
            "regardless of holding period (post April 2023 rules)."
        ]
    return ["Taxation details not available in corpus; refer to the scheme factsheet."]


def _fund_management(mf: dict) -> list[str]:
    managers = _val(mf, "fund_manager_details", required=True)
    if not isinstance(managers, list) or not managers:
        raise MissingRequiredField(
            "fund_manager_details is present but empty"
        )
    blocks: list[str] = []
    for mgr in managers:
        name = mgr.get("person_name", "Unknown")
        since_raw = mgr.get("date_from", "")
        since = _date(since_raw)
        edu = mgr.get("education", "").strip()
        exp = mgr.get("experience", "").strip()
        parts = [f"{name} has been managing this scheme since {since}."]
        if edu:
            parts.append(edu)
        if exp:
            parts.append(exp)
        # One bio = one block (kept intact, per architecture rule).
        blocks.append(" ".join(parts))
    return blocks


def _investment_objective(mf: dict) -> list[str]:
    desc = _val(mf, "description", required=True)
    return [desc.strip()]


def _fund_house(mf: dict) -> list[str]:
    amc_info = mf.get("amc_info") or {}
    scheme = mf.get("scheme_name", "This scheme")
    fund_house = mf.get("fund_house") or amc_info.get("name", "")
    launch = mf.get("launch_date", "")
    registrar = mf.get("registrar_agent", "")
    amc_aum = amc_info.get("aum")

    blocks: list[str] = []
    if fund_house:
        blocks.append(f"{scheme} is managed by {fund_house}.")
    if launch:
        blocks.append(f"This scheme was launched on {launch}.")
    if registrar:
        blocks.append(f"The registrar and transfer agent is {registrar}.")
    if amc_aum:
        blocks.append(f"Total AUM managed by {fund_house}: {_crore(amc_aum)}.")
    amc_desc = amc_info.get("description", "").strip()
    if amc_desc:
        blocks.append(amc_desc)
    return blocks


def _overview(mf: dict) -> list[str]:
    scheme = mf.get("scheme_name", "This scheme")
    category = mf.get("category", "")
    sub_cat = mf.get("sub_category", "")
    nav = mf.get("nav")
    nav_date = mf.get("nav_date", "")
    aum = mf.get("aum")
    # Riskometer: return_stats[0].risk is the live rating; nfo_risk is NFO-time.
    rs = (mf.get("return_stats") or [{}])[0]
    risk = rs.get("risk") or mf.get("nfo_risk", "")
    isin = mf.get("isin", "")
    plan = mf.get("plan_type", "")
    scheme_type = mf.get("scheme_type", "")

    blocks: list[str] = []
    if category or sub_cat:
        blocks.append(
            f"{scheme} is a {sub_cat} {category} mutual fund "
            f"({plan} plan, {scheme_type} option).".replace("  ", " ")
        )
    if nav is not None and nav_date:
        blocks.append(f"Current NAV: ₹{nav} as of {nav_date}.")
    if aum:
        blocks.append(f"Scheme AUM: {_crore(aum)}.")
    if risk:
        blocks.append(f"Riskometer classification: {risk}.")
    if isin:
        blocks.append(f"ISIN: {isin}.")
    return blocks


# ── Public entry point ─────────────────────────────────────────────────────────

_BUILDERS = {
    "overview":             _overview,
    "expense_ratio":        _expense_ratio,
    "exit_load":            _exit_load,
    "minimum_investment":   _minimum_investment,
    "benchmark":            _benchmark,
    "tax":                  _tax,
    "fund_management":      _fund_management,
    "investment_objective": _investment_objective,
    "fund_house":           _fund_house,
}

# Sanity-check at import time: every canonical tag has a builder.
assert set(_BUILDERS) == set(SECTION_TAGS), (
    f"Builder/tag mismatch: {set(SECTION_TAGS) - set(_BUILDERS)} missing builders"
)


def extract_sections(mf: dict) -> dict[str, list[str]]:
    """Build all 9 sections from the mfServerSideData dict.

    Raises MissingRequiredField if any required field is absent.
    Returns a dict keyed by all 9 section tags; each value is a list of strings.
    """
    # Validate required fields first so the error is clear.
    for field in REQUIRED_FIELDS:
        _val(mf, field, required=True)

    result: dict[str, list[str]] = {}
    for tag in SECTION_TAGS:
        try:
            result[tag] = _BUILDERS[tag](mf)
        except MissingRequiredField:
            raise
        except Exception as exc:
            # Non-required builder failure → empty section + warning, not crash.
            result[tag] = []
            import warnings
            warnings.warn(f"Section '{tag}' builder raised: {exc}", stacklevel=2)

    return result


def coverage(sections: dict[str, list[str]]) -> dict[str, int]:
    """Block count per section — used for smoke-test reporting."""
    return {tag: len(blocks) for tag, blocks in sections.items()}
