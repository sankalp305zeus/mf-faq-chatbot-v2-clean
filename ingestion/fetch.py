"""Phase 1 — fetch.

HTTP GET each corpus URL and save raw HTML to data/raw/ with a fetch timestamp.
Pure I/O: no parsing, no section logic. One file per scheme + a per-scheme
sidecar metadata JSON. A run-level manifest records overall status.

Run:  python -m ingestion.fetch
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from ingestion.config import RAW_DIR, env, load_corpus


def _headers() -> dict:
    return {
        "User-Agent": env(
            "FETCH_USER_AGENT",
            "Mozilla/5.0 (compatible; mf-faq-bot/0.1; +https://example.com)",
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
    }


def fetch_one(scheme: dict, timeout: int, retries: int) -> dict:
    """Fetch a single scheme URL. Returns a metadata record (never raises)."""
    url = scheme["source_url"]
    slug = scheme["slug"]
    attempt = 0
    last_err = None
    while attempt <= retries:
        attempt += 1
        try:
            resp = requests.get(url, headers=_headers(), timeout=timeout)
            resp.raise_for_status()
            html = resp.text
            html_path = RAW_DIR / f"{slug}.html"
            html_path.write_text(html, encoding="utf-8")
            meta = {
                "slug": slug,
                "scheme_name": scheme["scheme_name"],
                "source_url": url,
                "status": "ok",
                "http_status": resp.status_code,
                "content_length": len(html),
                # date used for the "Last updated from sources" footer downstream
                "last_updated": date.today().isoformat(),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "raw_path": str(html_path.relative_to(RAW_DIR.parent.parent)),
                "attempts": attempt,
            }
            (RAW_DIR / f"{slug}.meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )
            print(f"[ok]   {slug}  ({len(html):,} bytes, attempt {attempt})")
            return meta
        except Exception as exc:  # noqa: BLE401 — record and retry/move on
            last_err = str(exc)
            print(f"[warn] {slug}  attempt {attempt} failed: {last_err}")
            if attempt <= retries:
                time.sleep(2 * attempt)

    meta = {
        "slug": slug,
        "scheme_name": scheme["scheme_name"],
        "source_url": url,
        "status": "error",
        "error": last_err,
        "last_updated": date.today().isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "attempts": attempt - 1,
    }
    (RAW_DIR / f"{slug}.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"[fail] {slug}  giving up after {attempt - 1} attempts")
    return meta


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    corpus = load_corpus()
    schemes = corpus["schemes"]
    timeout = int(env("FETCH_TIMEOUT", "20"))
    retries = int(env("FETCH_RETRIES", "1"))

    print(f"Fetching {len(schemes)} corpus URLs -> {RAW_DIR}")
    results = [fetch_one(s, timeout, retries) for s in schemes]

    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "errors": sum(1 for r in results if r["status"] != "ok"),
        "schemes": results,
    }
    (RAW_DIR / "fetch_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Done. ok={manifest['ok']} errors={manifest['errors']}")
    # Non-zero exit only if everything failed (lets partial runs proceed).
    return 0 if manifest["ok"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
