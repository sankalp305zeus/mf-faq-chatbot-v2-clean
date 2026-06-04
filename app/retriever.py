"""Phase 3 — two-stage retrieval.

Stage 1: Resolve which scheme the query refers to (slug/name/alias matching,
         with a fallback to best-match scoring so ambiguous queries still
         return something rather than nothing).

Stage 2: Embed the query (BGE query prefix) → ChromaDB semantic search
         filtered by the resolved slug.  If a section intent is detected
         (e.g. "fund manager" → fund_management), the exact-section chunk is
         fetched first, then semantic top-k fills remaining slots.

Returns a RetrievalResult dataclass; callers (Phase 4/5) should inspect
.scheme_resolved before trusting the chunks.

Run standalone smoke test:
    python -m app.retriever
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings
from ingestion.config import load_corpus

# ── Constants ─────────────────────────────────────────────────────────────────

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

DEFAULT_TOP_K = 5

# Competitor AMC names that must block alias-only matches.
# If a query contains one of these tokens, generic industry aliases
# ("small cap", "large cap", etc.) must not resolve to an HDFC scheme.
_COMPETITOR_TOKENS: frozenset[str] = frozenset({
    "sbi", "axis", "nippon", "mirae", "icici", "kotak", "dsp", "uti",
    "aditya", "birla", "invesco", "franklin", "tata", "motilal", "sundaram",
    "canara", "quantum", "edelweiss", "parag", "whiteoak",
})

# Section intent: keywords (lowercase) → section tag.
# Longer / more specific phrases listed first so they win on match order.
# NOTE: bare "strategy" removed — replaced with "investment strategy" to prevent
# "exit strategy" from misfiring on this bucket (FAR-04).
_SECTION_INTENT: list[tuple[list[str], str]] = [
    (["expense ratio", "ter", "total expense", "annual fee", "management fee"], "expense_ratio"),
    (["exit load", "exit charges", "redemption charge", "stamp duty",
      "exit strategy"], "exit_load"),
    (["minimum sip", "min sip", "minimum investment", "min investment",
      "lumpsum", "lump sum", "sip amount"], "minimum_investment"),
    (["benchmark", "index", "nifty", "sensex", "bse", "nse"], "benchmark"),
    (["tax", "stcg", "ltcg", "capital gain", "taxation", "tax on"], "tax"),
    (["fund manager", "fund management", "who manages", "managed by",
      "portfolio manager", "manager"], "fund_management"),
    (["investment objective", "investment strategy", "objective",
      "investment goal", "fund aim", "aim of the fund"], "investment_objective"),
    (["fund house", "amc", "asset management", "about hdfc mf",
      "about hdfc mutual fund"], "fund_house"),
    (["nav", "aum", "isin", "riskometer", "category", "scheme type",
      "aum of", "net asset"], "overview"),
]


# ── Data contract ──────────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    query: str
    scheme_resolved: bool
    scheme_slug: Optional[str]
    scheme_name: Optional[str]
    source_url: Optional[str]
    section_intent: Optional[str]       # detected section tag, or None
    chunks: list[dict] = field(default_factory=list)
    # Each chunk: {id, text, source_url, scheme_name, section, slug, last_updated, score}
    disambiguation_hint: Optional[str] = None   # set when multiple schemes score close
    supported_schemes: list[str] = field(default_factory=list)
    # Populated when scheme_resolved=False so callers can tell the user what is supported


# ── Module-level lazy singletons (loaded once per process) ────────────────────

_model: Optional[SentenceTransformer] = None
_chroma_collection = None
_corpus: Optional[dict] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _get_collection(chroma_dir: Optional[Path] = None):
    global _chroma_collection
    if _chroma_collection is None:
        if chroma_dir is None:
            chroma_dir = settings.chroma_path
        client = chromadb.PersistentClient(path=str(chroma_dir))
        _chroma_collection = client.get_collection(settings.collection_name)
    return _chroma_collection


def _get_corpus() -> dict:
    global _corpus
    if _corpus is None:
        _corpus = load_corpus()
    return _corpus


# ── Stage 1: scheme resolution ────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _query_names_competitor(query_norm: str) -> bool:
    """Return True if the query contains a known non-HDFC AMC name."""
    tokens = set(query_norm.split())
    return bool(tokens & _COMPETITOR_TOKENS)


def _scheme_score(query_norm: str, scheme: dict) -> float:
    """Return a match score in [0, 1] for one scheme entry.

    Generic industry aliases (e.g. "small cap") score 0.0 when the query
    names a competitor AMC, preventing cross-AMC false positives (FAR-01).
    """
    slug_norm = _normalise(scheme["slug"])
    name_norm = _normalise(scheme["scheme_name"])
    aliases = [_normalise(a) for a in scheme.get("aliases", [])]

    # Exact slug or name
    if slug_norm == query_norm or name_norm == query_norm:
        return 1.0

    # Substring of slug or name
    if slug_norm in query_norm or name_norm in query_norm:
        return 0.9

    # Any alias appears as a word-boundary substring in the query.
    # Guard: if the query names a competitor AMC, alias-only matches are blocked.
    competitor_present = _query_names_competitor(query_norm)
    for alias in aliases:
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, query_norm):
            if competitor_present:
                # Competitor AMC named — alias overlap is coincidental, not a match.
                return 0.0
            return 0.85

    # Token overlap between query and (slug + name + aliases)
    query_tokens = set(query_norm.split())
    all_tokens: set[str] = set()
    for tok in (slug_norm + " " + name_norm).split():
        all_tokens.add(tok)
    for alias in aliases:
        all_tokens.update(alias.split())

    overlap = query_tokens & all_tokens
    # Remove stop tokens that appear everywhere ("hdfc", "fund", "direct", "growth")
    meaningful = overlap - {"hdfc", "fund", "direct", "growth", "plan", "the", "of"}
    if meaningful:
        if competitor_present:
            return 0.0
        return 0.5 + 0.1 * min(len(meaningful), 4)  # 0.6 – 0.9

    return 0.0


def resolve_scheme(
    query: str,
    corpus: Optional[dict] = None,
    min_score: float = 0.5,
) -> tuple[Optional[dict], float, Optional[str]]:
    """Return (best_scheme_entry, score, disambiguation_hint).

    If score < min_score no scheme is resolved (returns None, 0.0, None).
    If two schemes tie within 0.05, disambiguation_hint is set.
    """
    if corpus is None:
        corpus = _get_corpus()

    query_norm = _normalise(query)
    scored = [
        (scheme, _scheme_score(query_norm, scheme))
        for scheme in corpus["schemes"]
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_scheme, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0

    if best_score < min_score:
        return None, 0.0, None

    hint: Optional[str] = None
    if second_score >= best_score - 0.05 and second_score >= min_score:
        names = [s["scheme_name"] for s, sc in scored if sc >= best_score - 0.05]
        hint = f"Multiple schemes matched: {', '.join(names)}. Please specify."

    return best_scheme, best_score, hint


# ── Section intent detection ──────────────────────────────────────────────────

def detect_section_intent(query: str) -> Optional[str]:
    """Return the section tag most likely targeted by the query, or None."""
    q = _normalise(query)
    for keywords, section_tag in _SECTION_INTENT:
        for kw in keywords:
            # Use word-boundary match to avoid "ter" firing inside "after".
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, q):
                return section_tag
    return None


# ── Stage 2: semantic retrieval ───────────────────────────────────────────────

def _embed_query(query: str) -> list[float]:
    model = _get_model()
    return model.encode(
        BGE_QUERY_PREFIX + query,
        normalize_embeddings=True,
    ).tolist()


def _chroma_query(
    query: str,
    slug: str,
    top_k: int,
    collection=None,
    section_filter: Optional[str] = None,
) -> list[dict]:
    """Embed query and query ChromaDB, optionally filtered by section.

    When section_filter is set, the where clause restricts to that section
    (used for guaranteed section retrieval in FAR-03 fix).
    """
    if collection is None:
        collection = _get_collection()

    embedding = _embed_query(query)

    where: dict = {"slug": slug}
    if section_filter:
        where = {"$and": [{"slug": slug}, {"section": section_filter}]}

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    if not results["ids"] or not results["ids"][0]:
        return chunks

    for doc_id, text, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = round(1.0 - dist, 4)
        chunks.append({
            "id": doc_id,
            "text": text,
            "source_url": meta.get("source_url"),
            "scheme_name": meta.get("scheme_name"),
            "section": meta.get("section"),
            "slug": meta.get("slug"),
            "last_updated": meta.get("last_updated"),
            "score": score,
        })
    return chunks


def _retrieve_with_section_guarantee(
    query: str,
    slug: str,
    top_k: int,
    section_intent: Optional[str],
    collection=None,
) -> list[dict]:
    """Two-pass retrieval that guarantees the intent section appears at position 0.

    Pass 1 (when section_intent set): fetch the exact-section chunk(s) directly.
    Pass 2: semantic top-k over the full scheme, deduplicated against pass-1 IDs.
    Merge: exact-section chunks first, then semantic fillers up to top_k total.

    When section_intent is None, falls back to a single semantic pass.
    This fixes FAR-03: the intent section is always in the result regardless of
    whether it falls within the semantic top-k window.
    """
    if collection is None:
        collection = _get_collection()

    if not section_intent:
        return _chroma_query(query, slug, top_k, collection)

    # Pass 1: guaranteed section chunks (at most a handful per scheme)
    section_chunks = _chroma_query(query, slug, top_k, collection,
                                   section_filter=section_intent)
    section_ids = {c["id"] for c in section_chunks}

    # Pass 2: semantic top-k for context breadth, minus already-fetched IDs
    semantic_chunks = _chroma_query(query, slug, top_k, collection)
    filler = [c for c in semantic_chunks if c["id"] not in section_ids]

    combined = section_chunks + filler
    return combined[:top_k]


# ── Public API ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    chroma_dir: Optional[Path] = None,
    corpus: Optional[dict] = None,
    collection=None,
) -> RetrievalResult:
    """Full two-stage retrieval.

    Returns a RetrievalResult. Check .scheme_resolved before trusting chunks.
    If no scheme resolves, returns an empty result with scheme_resolved=False
    and supported_schemes populated for caller use (FAR-06).
    """
    if corpus is None:
        corpus = _get_corpus()

    scheme_entry, score, hint = resolve_scheme(query, corpus=corpus)
    section_intent = detect_section_intent(query)

    supported = [s["scheme_name"] for s in corpus["schemes"]]

    if scheme_entry is None:
        return RetrievalResult(
            query=query,
            scheme_resolved=False,
            scheme_slug=None,
            scheme_name=None,
            source_url=None,
            section_intent=section_intent,
            chunks=[],
            disambiguation_hint=hint,
            supported_schemes=supported,
        )

    if collection is None:
        collection = _get_collection(chroma_dir)

    ranked_chunks = _retrieve_with_section_guarantee(
        query, scheme_entry["slug"], top_k, section_intent, collection
    )

    return RetrievalResult(
        query=query,
        scheme_resolved=True,
        scheme_slug=scheme_entry["slug"],
        scheme_name=scheme_entry["scheme_name"],
        source_url=scheme_entry["source_url"],
        section_intent=section_intent,
        chunks=ranked_chunks,
        disambiguation_hint=hint,
        supported_schemes=[],  # not needed when scheme is resolved
    )


# ── Smoke test ────────────────────────────────────────────────────────────────

_SMOKE_QUERIES = [
    ("What is the expense ratio of HDFC Mid Cap fund?",         "expense_ratio"),
    ("Who manages the HDFC Small Cap Fund?",                    "fund_management"),
    ("Exit load for HDFC Defence Fund",                         "exit_load"),
    ("Minimum SIP investment in HDFC Gold ETF fund of fund",    "minimum_investment"),
    ("What is the benchmark index for HDFC Large Cap Fund?",    "benchmark"),
    ("Tax on HDFC Mid Cap redemption after 1 year",             "tax"),
    ("investment objective of hdfc defence fund",               "investment_objective"),
    ("Tell me about HDFC Large Cap fund house",                 "fund_house"),
]

_COMPETITOR_QUERIES = [
    "SBI small cap fund expense ratio",
    "Nippon large cap benchmark",
    "Axis mid cap exit load",
    "ICICI gold fund minimum investment",
    "Mirae defence ETF tax",
]


def _run_smoke() -> int:
    print("=== Phase 3 retrieval smoke test ===\n")
    errors = 0

    print("── Positive queries (should resolve + section-correct top chunk) ──\n")
    for query, expected_section in _SMOKE_QUERIES:
        result = retrieve(query)
        top = result.chunks[0] if result.chunks else None
        top_section = top["section"] if top else None
        section_ok = top_section == expected_section
        status = "OK" if result.scheme_resolved and result.chunks and section_ok else "FAIL"
        if status == "FAIL":
            errors += 1
        print(f"[{status}] {query!r}")
        print(f"       slug={result.scheme_slug}  intent={result.section_intent}"
              f"  top_section={top_section}  score={top['score'] if top else 'n/a'}")
        print()

    print("── Competitor queries (should NOT resolve) ──\n")
    for query in _COMPETITOR_QUERIES:
        result = retrieve(query)
        status = "OK" if not result.scheme_resolved else "FAIL"
        if status == "FAIL":
            errors += 1
        print(f"[{status}] {query!r}  resolved={result.scheme_resolved}"
              f"  slug={result.scheme_slug}")
    print()

    total = len(_SMOKE_QUERIES) + len(_COMPETITOR_QUERIES)
    print(f"Smoke test complete. {total - errors}/{total} passed.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_smoke())
