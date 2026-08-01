"""Bootstrap the pgvector-backed knowledge_corpus table.

Run once against a fresh Postgres 15+ instance (see docker-compose.yml):

    python db_setup.py

Reads DATABASE_URL from the environment / .env, e.g.:

    DATABASE_URL=postgresql://finbuddy:finbuddy_dev_password@localhost:5432/finbuddy_rag
"""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://finbuddy:finbuddy_dev_password@localhost:5432/finbuddy_rag",
)

# bge-small-en-v1.5 produces 384-dim embeddings.
EMBEDDING_DIM = 384

CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector;"

CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS knowledge_corpus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
);
"""

CREATE_PGCRYPTO = "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# NO ivfflat index at this corpus size. An earlier version of this file
# created one with lists=100 and it silently broke retrieval: IVFFlat is an
# APPROXIMATE nearest-neighbor index, and with only ~46 rows spread across
# 100 clusters, most clusters are empty or hold a single row -- probing the
# default 1 cluster missed the actual nearest neighbors entirely (verified:
# queries returned the wrong top document, and LIMIT 3 sometimes returned 0
# rows). Without any index, pgvector does an exact brute-force scan, which
# is both correct and fast at corpus sizes up to at least tens of thousands
# of rows. Add an ivfflat/hnsw index back only once the corpus is large
# enough for pgvector's own sizing guidance (roughly, lists ~= rows/1000 for
# ivfflat) to produce a sane cluster count -- and re-verify retrieval
# quality with real queries after doing so, the same way this was caught.
DROP_STALE_INDEX = "DROP INDEX IF EXISTS knowledge_corpus_embedding_idx;"

CREATE_METADATA_GIN_INDEX = """
CREATE INDEX IF NOT EXISTS knowledge_corpus_metadata_idx
ON knowledge_corpus USING gin (metadata);
"""


async def bootstrap() -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(CREATE_PGCRYPTO)
        await conn.execute(CREATE_EXTENSION)
        await conn.execute(CREATE_TABLE)
        await conn.execute(DROP_STALE_INDEX)
        await conn.execute(CREATE_METADATA_GIN_INDEX)
        count = await conn.fetchval("SELECT count(*) FROM knowledge_corpus;")
        print(f"knowledge_corpus ready (dim={EMBEDDING_DIM}), {count} rows present.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
