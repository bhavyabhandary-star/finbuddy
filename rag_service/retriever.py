"""search_corpus(): embed the query, cosine-similarity search against
knowledge_corpus, with a confidence gate per spec.

NO index on the embedding column at this corpus size -- see db_setup.py's
comment for why an ivfflat index actively broke retrieval here (46 rows is
far too few for lists=100). This does an exact brute-force scan, which is
correct and fast enough at this scale.

Confidence gate: pgvector's <=> operator returns cosine DISTANCE (0 =
identical). Similarity = 1 - distance. If the top result's similarity is
below CONFIDENCE_THRESHOLD, the caller should NOT generate an LLM answer --
route to a human coach instead (see main.py's /whatsapp-coach/respond).
"""

from __future__ import annotations

import json
import os

import asyncpg
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://finbuddy:finbuddy_dev_password@localhost:5432/finbuddy_rag",
)
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
CONFIDENCE_THRESHOLD = 0.70

_embedder: SentenceTransformer | None = None
_pool: asyncpg.Pool | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _embed_query(query: str) -> str:
    embedder = _get_embedder()
    vec = embedder.encode(query, normalize_embeddings=True)
    return "[" + ",".join(f"{x:.8f}" for x in vec.tolist()) + "]"


async def search_corpus(query: str, doc_type: str | None = None, top_k: int = 3) -> dict:
    """Returns {"results": [{content, metadata, similarity}], "low_confidence": bool}.

    `doc_type` filters the JSONB metadata BEFORE computing distances (per
    spec) -- cheaper and correct, since there's no reason to rank
    irrelevant-doc_type rows at all when a filter is given.
    """
    query_vector = _embed_query(query)
    pool = await get_pool()

    if doc_type:
        sql = (
            "SELECT content, metadata, 1 - (embedding <=> $1::vector) AS similarity "
            "FROM knowledge_corpus WHERE metadata->>'doc_type' = $2 "
            "ORDER BY embedding <=> $1::vector LIMIT $3"
        )
        args = (query_vector, doc_type, top_k)
    else:
        sql = (
            "SELECT content, metadata, 1 - (embedding <=> $1::vector) AS similarity "
            "FROM knowledge_corpus ORDER BY embedding <=> $1::vector LIMIT $2"
        )
        args = (query_vector, top_k)

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)

    results = [
        {
            "content": r["content"],
            "metadata": json.loads(r["metadata"]),  # asyncpg returns jsonb as raw text, not a parsed dict
            "similarity": round(float(r["similarity"]), 4),
        }
        for r in rows
    ]
    low_confidence = (not results) or results[0]["similarity"] < CONFIDENCE_THRESHOLD
    return {"results": results, "low_confidence": low_confidence, "query": query, "doc_type_filter": doc_type}


if __name__ == "__main__":
    import asyncio
    import json
    import sys

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    async def _demo() -> None:
        test_queries = [
            "why do you need my UPI data",
            "why was my limit reduced",
            "what is the weather like today",  # deliberately off-corpus
        ]
        for q in test_queries:
            result = await search_corpus(q, top_k=3)
            print(f"QUERY: {q}")
            print(f"  low_confidence={result['low_confidence']}")
            for r in result["results"]:
                print(f"  [{r['similarity']:.4f}] {r['metadata'].get('source_file')}")
            print()
        await close_pool()

    asyncio.run(_demo())
