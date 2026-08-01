"""Embed the chunked corpus (BAAI/bge-small-en-v1.5, 384-dim) and upsert
into knowledge_corpus. Idempotent: re-running clears and reloads rather
than appending duplicates, since the corpus is small and source-controlled
-- a real production corpus at scale would instead diff by content hash,
but for this size, full reload on every ingest run is simpler and safer
(no risk of stale duplicate chunks accumulating from doc edits).

Requires db_setup.py to have been run first (creates the table/extension).

Run: python -m rag_service.ingest
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import asyncpg
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from rag_service.chunker import chunk_corpus

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://finbuddy:finbuddy_dev_password@localhost:5432/finbuddy_rag",
)
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _metadata_json_safe(metadata: dict) -> dict:
    """frontmatter parses `last_verified: 2026-08-02` as a datetime.date --
    JSONB needs a plain string."""
    out = dict(metadata)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


async def ingest() -> None:
    print("Chunking corpus...")
    chunks = chunk_corpus()
    print(f"  {len(chunks)} chunks from the corpus")

    print(f"Loading embedding model {EMBEDDING_MODEL_NAME}...")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print("Embedding chunks...")
    texts = [c["content"] for c in chunks]
    embeddings = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("SELECT 1 FROM knowledge_corpus LIMIT 1;")  # sanity: table must already exist
    except asyncpg.UndefinedTableError:
        await conn.close()
        raise RuntimeError(
            "knowledge_corpus table doesn't exist -- run `python -m rag_service.db_setup` first."
        )

    try:
        async with conn.transaction():
            deleted = await conn.fetchval("WITH d AS (DELETE FROM knowledge_corpus RETURNING 1) SELECT count(*) FROM d;")
            print(f"Cleared {deleted} existing rows.")

            for chunk, embedding in zip(chunks, embeddings):
                metadata = _metadata_json_safe(chunk["metadata"])
                embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding.tolist()) + "]"
                await conn.execute(
                    "INSERT INTO knowledge_corpus (content, embedding, metadata) VALUES ($1, $2::vector, $3::jsonb)",
                    chunk["content"],
                    embedding_str,
                    json.dumps(metadata),
                )
        count = await conn.fetchval("SELECT count(*) FROM knowledge_corpus;")
        print(f"Ingest complete: {count} rows in knowledge_corpus.")
    finally:
        await conn.close()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(ingest())
