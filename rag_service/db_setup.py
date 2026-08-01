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

# ivfflat index for cosine-distance search once the corpus has enough rows;
# harmless (and near-instant) on a small seed corpus too.
CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS knowledge_corpus_embedding_idx
ON knowledge_corpus USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
"""

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
        await conn.execute(CREATE_INDEX)
        await conn.execute(CREATE_METADATA_GIN_INDEX)
        count = await conn.fetchval("SELECT count(*) FROM knowledge_corpus;")
        print(f"knowledge_corpus ready (dim={EMBEDDING_DIM}), {count} rows present.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
