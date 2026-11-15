"""Groq generation call for the WhatsApp coach. Isolated in its own module
so tests can monkeypatch `generate` directly instead of needing a live
GROQ_API_KEY (see tests/test_rag_pipeline.py's mock harness).
"""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

# Groq shut down llama-3.3-70b-versatile on 2026-08-16 (their deprecations page
# names openai/gpt-oss-120b as the replacement); CI began failing with
# model_not_found. Override with GROQ_MODEL without a code change if it moves again.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

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
        # gpt-oss is a reasoning model: its reasoning tokens count against the cap, so keep the
        # effort low and leave room, or a 500-token cap can truncate the visible answer.
        max_tokens=1200,
        extra_body={"reasoning_effort": "low"},
    )
    return normalise_typography(completion.choices[0].message.content)


def normalise_typography(text: str | None) -> str | None:
    """gpt-oss writes typographic spaces (U+202F narrow no-break, U+00A0) and "5 %" with a
    space before the percent sign. That breaks exact-text checks on figures like "5%" and
    renders oddly in WhatsApp, so use plain spaces and attach "%" to its number."""
    if text is None:
        return None
    text = text.replace(" ", " ").replace(" ", " ")
    return re.sub(r"(\d) +%", r"\1%", text)
