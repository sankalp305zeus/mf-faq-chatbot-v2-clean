"""Phase 1 — parse.

Reads raw HTML from data/raw/, extracts the mfServerSideData dict from
Groww's __NEXT_DATA__ SSR payload, builds structured sections via
ingestion.sections, and writes data/processed/<slug>.sections.json.

Each output document carries the full metadata needed downstream for
citation and footer: source_url, scheme_name, section, last_updated.

Fails loudly if __NEXT_DATA__ is absent or any required field is missing
(value-presence gate recommended by Sentinel review).

Run:  python -m ingestion.parse
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ingestion.config import PROCESSED_DIR, RAW_DIR, load_corpus
from ingestion.sections import MissingRequiredField, coverage, extract_sections


def _load_next_data(html: str, slug: str) -> dict:
    """Extract and return mfServerSideData from __NEXT_DATA__. Raises on failure."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        raise ValueError(f"{slug}: __NEXT_DATA__ script tag not found in HTML")
    try:
        payload = json.loads(tag.string)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{slug}: failed to parse __NEXT_DATA__ JSON: {exc}") from exc

    try:
        mf = payload["props"]["pageProps"]["mfServerSideData"]
    except KeyError as exc:
        raise ValueError(
            f"{slug}: expected path props.pageProps.mfServerSideData missing: {exc}"
        ) from exc

    if not isinstance(mf, dict):
        raise ValueError(f"{slug}: mfServerSideData is not a dict (got {type(mf)})")

    return mf


def parse_one(scheme: dict) -> dict:
    slug = scheme["slug"]
    html_path = RAW_DIR / f"{slug}.html"
    meta_path = RAW_DIR / f"{slug}.meta.json"

    if not html_path.exists():
        print(f"[skip] {slug}  — no raw HTML (run fetch first)")
        return {"slug": slug, "status": "missing_raw"}

    raw_meta: dict = {}
    if meta_path.exists():
        raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    last_updated = raw_meta.get("last_updated", datetime.now(timezone.utc).date().isoformat())

    html = html_path.read_text(encoding="utf-8")

    try:
        mf = _load_next_data(html, slug)
    except ValueError as exc:
        print(f"[fail] {slug}  — {exc}")
        return {"slug": slug, "status": "error", "error": str(exc)}

    try:
        sections = extract_sections(mf)
    except MissingRequiredField as exc:
        print(f"[fail] {slug}  — {exc}")
        return {"slug": slug, "status": "error", "error": str(exc)}

    cov = coverage(sections)
    populated = sum(1 for c in cov.values() if c > 0)

    record = {
        "slug": slug,
        "scheme_name": scheme["scheme_name"],
        "source_url": scheme["source_url"],
        "category": scheme.get("category"),
        "last_updated": last_updated,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "total_blocks": sum(cov.values()),
        "coverage": cov,
        "sections": sections,
    }

    out_path = PROCESSED_DIR / f"{slug}.sections.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ok]   {slug}  {sum(cov.values())} blocks, {populated}/9 sections populated")
    record["status"] = "ok"
    return record


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    corpus = load_corpus()
    schemes = corpus["schemes"]
    print(f"Parsing {len(schemes)} schemes  {RAW_DIR} -> {PROCESSED_DIR}")

    results = [parse_one(s) for s in schemes]
    ok = sum(1 for r in results if r.get("status") == "ok")
    errors = [r for r in results if r.get("status") not in ("ok", "missing_raw")]

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  {e['slug']}: {e.get('error')}")

    print(f"Done. parsed={ok}/{len(results)}")
    # Non-zero exit if any scheme that was fetched failed to parse.
    fetched = sum(1 for r in results if r.get("status") != "missing_raw")
    return 0 if ok == fetched else 1


if __name__ == "__main__":
    sys.exit(main())
