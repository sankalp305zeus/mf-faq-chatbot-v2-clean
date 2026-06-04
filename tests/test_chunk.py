"""Phase 2 unit tests — chunker.

All in-memory; no filesystem or network.
"""
from __future__ import annotations

import pytest

from ingestion.chunk import chunk_scheme, _PER_BLOCK_SECTIONS
from ingestion.config import SECTION_TAGS


def _minimal_record(**overrides) -> dict:
    base = {
        "slug": "hdfc-test-fund-direct-growth",
        "scheme_name": "HDFC Test Fund Direct Growth",
        "source_url": "https://groww.in/mutual-funds/hdfc-test-fund-direct-growth",
        "last_updated": "2026-06-04",
        "sections": {
            "overview": ["Category sentence.", "NAV sentence.", "AUM sentence."],
            "expense_ratio": ["Expense ratio is 0.73%."],
            "exit_load": ["Exit load of 1%.", "Stamp duty 0.005%."],
            "minimum_investment": ["Min SIP ₹100.", "Min lumpsum ₹100.", "No lock-in."],
            "benchmark": ["Benchmark: NIFTY TRI."],
            "tax": ["STCG 20%, LTCG 12.5%."],
            "fund_management": [
                "Alice has been managing since 01-Jan-2020. MBA.",
                "Bob has been managing since 01-Jun-2022. CA.",
            ],
            "investment_objective": ["Seeks long-term capital appreciation."],
            "fund_house": ["Managed by HDFC MF.", "Launched 2013.", "Registrar CAMS."],
        },
    }
    base.update(overrides)
    return base


# ── Schema / structure ────────────────────────────────────────────────────────

def test_chunk_ids_are_unique():
    chunks = chunk_scheme(_minimal_record())
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_every_chunk_has_required_metadata_keys():
    required = {"id", "text", "source_url", "scheme_name", "section", "slug", "last_updated"}
    for chunk in chunk_scheme(_minimal_record()):
        assert required <= set(chunk.keys()), f"Missing keys in {chunk['id']}"


def test_id_format_slug_section_n():
    chunks = chunk_scheme(_minimal_record())
    for c in chunks:
        parts = c["id"].split("#")
        assert len(parts) == 3
        assert parts[0] == "hdfc-test-fund-direct-growth"
        assert parts[1] in SECTION_TAGS
        assert parts[2].isdigit()


def test_metadata_values_propagated():
    chunks = chunk_scheme(_minimal_record())
    for c in chunks:
        assert c["source_url"] == "https://groww.in/mutual-funds/hdfc-test-fund-direct-growth"
        assert c["scheme_name"] == "HDFC Test Fund Direct Growth"
        assert c["last_updated"] == "2026-06-04"
        assert c["slug"] == "hdfc-test-fund-direct-growth"


# ── Merge vs per-block logic ──────────────────────────────────────────────────

def test_fund_management_one_chunk_per_bio():
    chunks = chunk_scheme(_minimal_record())
    fm_chunks = [c for c in chunks if c["section"] == "fund_management"]
    assert len(fm_chunks) == 2
    assert "Alice" in fm_chunks[0]["text"]
    assert "Bob" in fm_chunks[1]["text"]


def test_fund_management_bio_not_merged():
    chunks = chunk_scheme(_minimal_record())
    fm_chunks = [c for c in chunks if c["section"] == "fund_management"]
    # Neither bio should contain the other manager's name
    assert "Bob" not in fm_chunks[0]["text"]
    assert "Alice" not in fm_chunks[1]["text"]


def test_non_fund_management_sections_merged_to_one_chunk():
    chunks = chunk_scheme(_minimal_record())
    for section in SECTION_TAGS:
        if section in _PER_BLOCK_SECTIONS:
            continue
        section_chunks = [c for c in chunks if c["section"] == section]
        record_blocks = _minimal_record()["sections"].get(section, [])
        if record_blocks:
            assert len(section_chunks) == 1, (
                f"Section '{section}' should merge to 1 chunk, got {len(section_chunks)}"
            )


def test_merged_chunk_contains_all_blocks():
    chunks = chunk_scheme(_minimal_record())
    overview_chunk = next(c for c in chunks if c["section"] == "overview")
    assert "Category sentence." in overview_chunk["text"]
    assert "NAV sentence." in overview_chunk["text"]
    assert "AUM sentence." in overview_chunk["text"]


def test_empty_section_produces_no_chunk():
    record = _minimal_record()
    record["sections"]["benchmark"] = []
    chunks = chunk_scheme(record)
    assert not any(c["section"] == "benchmark" for c in chunks)


# ── Total chunk count ─────────────────────────────────────────────────────────

def test_total_chunk_count():
    # 8 non-per-block sections (1 merged chunk each) + 2 fund_management bios = 10
    chunks = chunk_scheme(_minimal_record())
    assert len(chunks) == 10
