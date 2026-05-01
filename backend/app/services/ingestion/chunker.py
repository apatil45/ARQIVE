"""
Chunker: sliding window 400 tokens, 60 overlap. Min 50 tokens per chunk.
Uses word-based approximation: ~1.35 tokens/word (English). Tables/headers/lists simplified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from app.services.ingestion.parser import PageText

CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 60
MIN_CHUNK_TOKENS = 50
# Word approximation: 1 token ~= 1.35 words
CHUNK_SIZE_WORDS = int(CHUNK_SIZE_TOKENS / 1.35)   # ~296
CHUNK_OVERLAP_WORDS = int(CHUNK_OVERLAP_TOKENS / 1.35)  # ~44
MIN_CHUNK_WORDS = int(MIN_CHUNK_TOKENS / 1.35)     # ~37

MAX_TABLE_CHUNK_TOKENS = 800
MAX_CODE_CHUNK_TOKENS = 800


@dataclass
class ChunkResult:
    text: str
    page_number: int
    chunk_index: int
    token_count: int


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _estimate_tokens(text: str) -> int:
    return int(_word_count(text) * 1.35)


def _sliding_chunks(text: str, page_number: int) -> Iterator[ChunkResult]:
    """Split text by sliding window. Yields ChunkResult with 0-based chunk_index."""
    words = _words(text)
    if not words:
        return
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE_WORDS, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)
        tok = _estimate_tokens(chunk_text)
        if tok >= MIN_CHUNK_TOKENS or end >= len(words):
            yield ChunkResult(
                text=chunk_text,
                page_number=page_number,
                chunk_index=idx,
                token_count=tok,
            )
            idx += 1
        start += CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS
        if start >= len(words):
            break


def chunk_pages(pages: list[PageText]) -> list[ChunkResult]:
    """
    Chunk a list of page-level texts. Preserves page number per chunk.
    Tables/lists/code: simplified — no mid-list split (we treat by paragraph when possible).
    """
    result: list[ChunkResult] = []
    global_idx = 0
    for p in pages:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        for c in _sliding_chunks(text, p.get("page_number", 1)):
            result.append(
                ChunkResult(
                    text=c.text,
                    page_number=c.page_number,
                    chunk_index=global_idx,
                    token_count=c.token_count,
                )
            )
            global_idx += 1
    return result
