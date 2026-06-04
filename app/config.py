"""Central configuration for the entire project.

Reads from environment variables (populated from .env via python-dotenv).
Import `settings` anywhere — ingestion scripts, app layer, schedulers, tests.

Usage:
    from app.config import settings

    settings.embedding_model   # str
    settings.chroma_path       # pathlib.Path (absolute)
    settings.groq_api_key      # call settings.require_groq() to validate first

Testing:
    Use monkeypatch.setenv() or a .env.test file before importing this module.
    The module calls load_dotenv() once; subsequent imports reuse the cached object.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve repo root from this file's location (app/config.py → project root).
_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the repo root.  override=False means real env vars always win,
# so CI / Docker / production can inject values without being overridden by a
# checked-in .env.  dotenv_path is explicit so the file is found regardless of
# the working directory the process was launched from.
load_dotenv(dotenv_path=_ROOT / ".env", override=False)


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Config error: {name}={raw!r} is not a valid integer") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


class _Settings:
    """Immutable-at-read settings bag.  All values resolved once at import time."""

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = _get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    # ── Vector store ──────────────────────────────────────────────────────────
    # CHROMA_PATH may be relative (resolved against repo root) or absolute.
    _chroma_raw: str = _get("CHROMA_PATH", "data/index")
    chroma_path: Path = (
        Path(_chroma_raw) if Path(_chroma_raw).is_absolute()
        else _ROOT / _chroma_raw
    )
    collection_name: str = _get("COLLECTION_NAME", "mf_faq")

    # ── LLM (Groq) — values stored but not validated here ────────────────────
    groq_api_key: str = _get("GROQ_API_KEY", "")
    groq_model: str = _get("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ── Ingestion ─────────────────────────────────────────────────────────────
    fetch_timeout: int = _get_int("FETCH_TIMEOUT", 20)
    fetch_retries: int = _get_int("FETCH_RETRIES", 1)
    fetch_user_agent: str = _get(
        "FETCH_USER_AGENT",
        "Mozilla/5.0 (compatible; mf-faq-bot/0.1; +https://example.com)",
    )

    # ── API / server ──────────────────────────────────────────────────────────
    rate_limit: str = _get("RATE_LIMIT", "30/minute")
    mock_llm: bool = _get_bool("MOCK_LLM", False)

    # ── Observability ─────────────────────────────────────────────────────────
    log_level: str = _get("LOG_LEVEL", "INFO").upper()

    # ── Repo root (useful for path construction elsewhere) ────────────────────
    root: Path = _ROOT

    def require_groq(self) -> str:
        """Return groq_api_key, raising RuntimeError if it is empty.

        Call this lazily (only on the LLM code path), not at module import,
        so ingestion and retrieval work without GROQ_API_KEY set.
        """
        if not self.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Add it to .env or export it in your environment."
            )
        return self.groq_api_key


settings = _Settings()

# Configure root logger once.  Modules that use logging.getLogger(__name__)
# inherit this level automatically.
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
