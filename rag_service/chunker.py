"""Paragraph/header-aware semantic chunking for the FinBuddy RAG corpus.

Per spec: NEVER fixed character-count splitting -- a condition split from
its parent clause is a correctness bug in a legal corpus (e.g. "the DLG cap
is 5%" separated from the clause defining what DLG is), not a cosmetic one.

Strategy:
  1. Split each document on markdown `## ` headers first (a header boundary
     is always a safe place to cut -- it's a real topic boundary the author
     put there deliberately).
  2. Within a section, accumulate whole paragraphs (split on blank lines)
     up to max_chars. Never cut a paragraph in half to hit a size target.
  3. When starting a new chunk, carry over the trailing whole paragraph(s)
     of the previous chunk (10-15% of max_chars) so a definition
     introduced right before a boundary isn't orphaned from the rule that
     depends on it.
  4. Only if a SINGLE paragraph exceeds max_chars on its own (a fallback
     case, not expected in this authored corpus) does this fall back to a
     sentence-boundary split -- still never a mid-sentence cut.

Run: python -m rag_service.chunker  (sanity-checks against the real corpus)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import frontmatter

CORPUS_DIR = Path(__file__).resolve().parent / "finbuddy_rag_corpus"

MAX_CHARS = 1100
OVERLAP_RATIO = 0.125  # 12.5%, within the 10-15% spec range

REQUIRED_METADATA_KEYS = {"doc_type", "regulator", "effective_year", "audience"}


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences_fallback(paragraph: str, max_chars: int) -> list[str]:
    """Only used if a single paragraph exceeds max_chars on its own."""
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    chunks, current = [], ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > max_chars:
            chunks.append(current.strip())
            current = s
        else:
            current = f"{current} {s}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


MIN_LEADING_SECTION_CHARS = 150  # verified against the real corpus: title-only leads are 37-86 chars, real intros are 258+


def split_into_sections(body: str) -> list[str]:
    """Splits on `## ` headers. Content before the first header (title/intro)
    is its own leading section -- UNLESS that leading section is just the H1
    title with no real intro paragraph (a bug found via Gate B testing: a
    title-only chunk like "# RBI ... DLG Cap" can embed with high similarity
    to a query using similar phrasing, while carrying zero actual answer
    content, and out-rank the chunk that actually has the number in it. If
    the leading section has less than MIN_LEADING_SECTION_CHARS beyond
    trivial whitespace, fold it into the first real section instead of
    emitting it as its own retrievable-but-empty chunk."""
    lines = body.split("\n")
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    texts = ["\n".join(s).strip() for s in sections if "\n".join(s).strip()]
    if len(texts) > 1 and not texts[0].startswith("## ") and len(texts[0]) < MIN_LEADING_SECTION_CHARS:
        texts = [texts[0] + "\n\n" + texts[1]] + texts[2:]
    return texts


def chunk_section(section_text: str, max_chars: int, overlap_ratio: float) -> list[str]:
    paragraphs = split_paragraphs(section_text)
    # Expand any single paragraph that alone exceeds max_chars.
    expanded = []
    for p in paragraphs:
        if len(p) > max_chars:
            expanded.extend(split_sentences_fallback(p, max_chars))
        else:
            expanded.append(p)
    paragraphs = expanded

    overlap_chars = int(max_chars * overlap_ratio)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current and current_len + para_len + 2 > max_chars:
            chunks.append("\n\n".join(current))
            # Budget overlap so it never pushes this new chunk over max_chars
            # on its own -- the incoming paragraph is mandatory (it's a whole
            # semantic unit, never split), so overlap yields to it, not the
            # other way around.
            overlap_budget = max(0, min(overlap_chars, max_chars - para_len))
            overlap_paras: list[str] = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) > overlap_budget:
                    break
                overlap_paras.insert(0, p)
                overlap_len += len(p)
            current = overlap_paras + [para]
            current_len = overlap_len + para_len
        else:
            current.append(para)
            current_len += para_len + 2

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_document(path: str | Path) -> list[dict[str, Any]]:
    post = frontmatter.load(str(path))
    metadata = dict(post.metadata)

    missing = REQUIRED_METADATA_KEYS - metadata.keys()
    if missing:
        raise ValueError(f"{path}: missing required metadata keys {missing}")

    sections = split_into_sections(post.content)
    chunks = []
    for section in sections:
        for chunk_text in chunk_section(section, MAX_CHARS, OVERLAP_RATIO):
            chunks.append(
                {
                    "content": chunk_text,
                    "metadata": {**metadata, "source_file": str(Path(path).relative_to(CORPUS_DIR.parent))},
                }
            )
    return chunks


def chunk_corpus(corpus_dir: str | Path = CORPUS_DIR) -> list[dict[str, Any]]:
    all_chunks = []
    for md_path in sorted(Path(corpus_dir).rglob("*.md")):
        all_chunks.extend(chunk_document(md_path))
    return all_chunks


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    chunks = chunk_corpus()
    print(f"Total chunks across corpus: {len(chunks)}")
    by_doc: dict[str, int] = {}
    for c in chunks:
        by_doc[c["metadata"]["source_file"]] = by_doc.get(c["metadata"]["source_file"], 0) + 1
    for doc, n in sorted(by_doc.items()):
        print(f"  {doc}: {n} chunk(s)")

    lengths = [len(c["content"]) for c in chunks]
    print(f"\nchunk length: min={min(lengths)} max={max(lengths)} mean={sum(lengths)/len(lengths):.0f}")
    print(f"(target max_chars={MAX_CHARS}, overlap_ratio={OVERLAP_RATIO})")

    print("\n--- sample chunk ---")
    print(chunks[0]["metadata"])
    print(chunks[0]["content"][:300])
