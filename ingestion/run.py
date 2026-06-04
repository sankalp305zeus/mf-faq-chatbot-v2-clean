"""Ingestion entrypoint — atomic pipeline runner.

Chains: fetch → parse → chunk → index.

Called by the daily scheduler (scheduler/daily.py) and usable directly for
ad-hoc manual refreshes.  The chat API continues serving the previous index
until ChromaDB's upsert + persist completes (ChromaDB's own atomicity).

Exit codes:
  0 — all stages succeeded
  1 — one or more stages failed (details printed to stdout)

Run:  python -m ingestion.run
      python -m ingestion.run --skip-fetch   (re-parse/chunk/index existing raw)
"""
from __future__ import annotations

import sys
import time


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(skip_fetch: bool = False) -> int:
    start = time.monotonic()
    print(f"[{_ts()}] ingestion/run.py started  skip_fetch={skip_fetch}")

    # Stage 1 — fetch
    if not skip_fetch:
        print(f"\n── Stage 1: fetch ──────────────────────────────────────")
        from ingestion.fetch import main as fetch_main
        rc = fetch_main()
        if rc != 0:
            print(f"[{_ts()}] fetch stage failed (exit {rc}) — aborting")
            return 1

    # Stage 2 — parse
    print(f"\n── Stage 2: parse ──────────────────────────────────────")
    from ingestion.parse import main as parse_main
    rc = parse_main()
    if rc != 0:
        print(f"[{_ts()}] parse stage failed (exit {rc}) — aborting")
        return 1

    # Stage 3 — chunk
    print(f"\n── Stage 3: chunk ──────────────────────────────────────")
    from ingestion.chunk import main as chunk_main
    rc = chunk_main()
    if rc != 0:
        print(f"[{_ts()}] chunk stage failed (exit {rc}) — aborting")
        return 1

    # Stage 4 — embed + index
    print(f"\n── Stage 4: embed + index ──────────────────────────────")
    from ingestion.index import main as index_main
    rc = index_main()
    if rc != 0:
        print(f"[{_ts()}] index stage failed (exit {rc}) — aborting")
        return 1

    elapsed = time.monotonic() - start
    print(f"\n[{_ts()}] ingestion complete  elapsed={elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    skip = "--skip-fetch" in sys.argv
    sys.exit(main(skip_fetch=skip))
