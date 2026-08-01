"""Groq generation call for the WhatsApp coach. Isolated in its own module
so tests can monkeypatch `generate` directly instead of needing a live
GROQ_API_KEY (see tests/test_rag_pipeline.py's mock harness).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set -- sign up free at console.groq.com, create an API key, "
                "and put it in rag_service/.env"
            )
        _client = AsyncGroq(api_key=api_key)
    return _client


async def generate(system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    completion = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # low -- this is a compliance-adjacent grounded-answer task, not creative writing
        max_tokens=500,
    )
    return completion.choices[0].message.content
