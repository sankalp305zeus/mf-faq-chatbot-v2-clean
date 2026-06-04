"""Phase 1 completion / Phase 2 input — chunker.

Reads data/processed/<slug>.sections.json (output of parse.py) and produces
a flat list of Chunk dicts written to data/processed/<slug>.chunks.json.

Chunking strategy (confirmed by data inspection, 2026-06-04):
  - All section blocks are 2–71 tokens each — well under any split threshold.
  - fund_management: one chunk per manager bio (already one block per bio).
    Bios must stay intact (architecture rule).
  - All other sections: merge all blocks for that section into one chunk,
    joined by a single space.  This maximises context per retrieval hit.
  - No overlap, no splitting — the corpus is too small for either to matter.

Chunk schema (matches ChromaDB document + metadata contract from ARCHITECTURE.md):
  {
    "id":          "<slug>#<section>#<n>",
    "text":        "<embeddable string>",
    "source_url":  "<corpus URL>",
    "scheme_name": "<human name>",
    "section":     "<one of 9 tags>",
    "slug":        "<scheme slug>",
    "last_updated":"<YYYY-MM-DD from fetch metadata>"
  }

Run:  python -m ingestion.chunk
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ingestion.config import PROCESSED_DIR, SECTION_TAGS

# fund_management is the only section where blocks must NOT be merged.
_PER_BLOCK_SECTIONS = {"fund_management"}


def chunk_scheme(record: dict) -> list[dict]:
    """Produce chunks for one scheme record (output of parse_one)."""
    slug = record["slug"]
    scheme_name = record["scheme_name"]
    source_url = record["source_url"]
    last_updated = record["last_updated"]
    sections: dict[str, list[str]] = record["sections"]

    chunks: list[dict] = []

    for section in SECTION_TAGS:
        blocks = sections.get(section, [])
        if not blocks:
            continue  # section absent for this scheme — skip

        if section in _PER_BLOCK_SECTIONS:
            # One chunk per block (one per manager bio).
            for i, block in enumerate(blocks):
                chunks.append({
                    "id": f"{slug}#{section}#{i}",
                    "text": block,
                    "source_url": source_url,
                    "scheme_name": scheme_name,
                    "section": section,
                    "slug": slug,
                    "last_updated": last_updated,
                })
        else:
            # Merge all blocks for this section into one chunk.
            merged = " ".join(blocks)
            chunks.append({
                "id": f"{slug}#{section}#0",
                "text": merged,
                "source_url": source_url,
                "scheme_name": scheme_name,
                "section": section,
                "slug": slug,
                "last_updated": last_updated,
            })

    return chunks


def chunk_all(processed_dir: Path = PROCESSED_DIR) -> list[dict]:
    """Chunk every sections.json in processed_dir. Returns all chunks."""
    all_chunks: list[dict] = []

    section_files = sorted(processed_dir.glob("*.sections.json"))
    if not section_files:
        raise FileNotFoundError(
            f"No *.sections.json files found in {processed_dir}. "
            "Run ingestion/parse.py first."
        )

    for path in section_files:
        record = json.loads(path.read_text(encoding="utf-8"))
        chunks = chunk_scheme(record)
        all_chunks.extend(chunks)

        # Write per-scheme chunks file alongside the sections file.
        out_path = processed_dir / f"{record['slug']}.chunks.json"
        out_path.write_text(
            json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[ok]   {record['slug']}  {len(chunks)} chunks")

    return all_chunks


def main() -> int:
    print(f"Chunking processed sections -> {PROCESSED_DIR}")
    try:
        chunks = chunk_all()
    except FileNotFoundError as exc:
        print(f"[fail] {exc}")
        return 1

    # Summary stats
    from collections import Counter
    section_counts = Counter(c["section"] for c in chunks)
    scheme_counts = Counter(c["slug"] for c in chunks)

    print(f"\nTotal chunks: {len(chunks)}")
    print("By section:")
    for sec in SECTION_TAGS:
        print(f"  {sec:25} {section_counts.get(sec, 0)}")
    print(f"By scheme: {dict(scheme_counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
