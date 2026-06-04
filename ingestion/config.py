"""Shared paths and corpus loading for the ingestion pipeline."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# Repo root = parent of the ingestion/ package.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "corpus.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

# The 9 logical sections defined in ARCHITECTURE.md. Order is canonical.
SECTION_TAGS = [
    "overview",
    "expense_ratio",
    "exit_load",
    "minimum_investment",
    "benchmark",
    "tax",
    "fund_management",
    "investment_objective",
    "fund_house",
]


def load_corpus(path: Path = CONFIG_PATH) -> dict:
    """Load and lightly validate config/corpus.yaml."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    schemes = data.get("schemes", [])
    if not schemes:
        raise ValueError(f"No schemes defined in {path}")
    for s in schemes:
        for field in ("slug", "scheme_name", "source_url"):
            if not s.get(field):
                raise ValueError(f"Scheme missing required field '{field}': {s}")
    return data


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)
