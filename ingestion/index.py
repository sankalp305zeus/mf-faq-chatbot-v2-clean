"""Phase 2 — embed + index.

Embeds all chunks produced by chunk.py using BGE-small-en-v1.5 (local,
sentence-transformers) and upserts them into a persistent ChromaDB collection.

Design decisions (from RESEARCH.md + ARCHITECTURE.md):
  - BGE-small-en-v1.5: free, local, 384-dim, sufficient for 51 short factual chunks.
  - ChromaDB (persistent): native metadata filtering + upsert; FAISS lacks both.
  - Upsert semantics: safe to re-run; existing documents are replaced atomically
    per chunk ID, so a re-index from daily ingestion is idempotent.
  - Collection name: "mf_faq" — fixed, single collection for all schemes.
  - Metadata stored per chunk matches the contract in ARCHITECTURE.md:
      source_url, scheme_name, section, slug, last_updated.
  - Embedding model is loaded once per process and reused across all chunks.

Run:  python -m ingestion.index
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from ingestion.config import PROCESSED_DIR, ROOT, env

COLLECTION_NAME = "mf_faq"
EMBED_MODEL_NAME = env("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
# BGE-small requires a query prefix for retrieval; documents are embedded plain.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def get_chroma_client(chroma_dir: Path) -> chromadb.PersistentClient:
    chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_dir))


def load_all_chunks(processed_dir: Path = PROCESSED_DIR) -> list[dict]:
    chunk_files = sorted(processed_dir.glob("*.chunks.json"))
    if not chunk_files:
        raise FileNotFoundError(
            f"No *.chunks.json files found in {processed_dir}. "
            "Run ingestion/chunk.py first."
        )
    all_chunks: list[dict] = []
    for path in chunk_files:
        all_chunks.extend(json.loads(path.read_text(encoding="utf-8")))
    return all_chunks


def build_index(
    chunks: list[dict] | None = None,
    chroma_dir: Path | None = None,
    model_name: str = EMBED_MODEL_NAME,
) -> dict[str, Any]:
    """Embed chunks and upsert into ChromaDB. Returns a stats dict."""
    if chunks is None:
        chunks = load_all_chunks()
    if chroma_dir is None:
        chroma_dir = ROOT / env("CHROMA_DIR", "data/index")

    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"Model loaded. Embedding dim: {embedding_dim}")

    texts = [c["text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks …")
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,  # cosine similarity via dot product
    )
    print(f"Embeddings generated: shape {embeddings.shape}")

    client = get_chroma_client(chroma_dir)

    # Get or create collection (cosine distance matches normalized embeddings).
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c["id"] for c in chunks]
    metadatas = [
        {
            "source_url":  c["source_url"],
            "scheme_name": c["scheme_name"],
            "section":     c["section"],
            "slug":        c["slug"],
            "last_updated": c["last_updated"],
        }
        for c in chunks
    ]

    print(f"Upserting {len(chunks)} chunks into collection '{COLLECTION_NAME}' …")
    collection.upsert(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
    )
    # PersistentClient auto-persists on every write; no explicit flush needed.

    count = collection.count()
    print(f"Collection '{COLLECTION_NAME}': {count} documents persisted.")

    return {
        "model": model_name,
        "embedding_dim": embedding_dim,
        "chunks_embedded": len(chunks),
        "collection": COLLECTION_NAME,
        "collection_count": count,
        "chroma_dir": str(chroma_dir),
    }


def main() -> int:
    try:
        stats = build_index()
    except FileNotFoundError as exc:
        print(f"[fail] {exc}")
        return 1

    print("\n=== Phase 2 index summary ===")
    for k, v in stats.items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
