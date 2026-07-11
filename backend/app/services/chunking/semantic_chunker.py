"""
Semantic chunker.

Rules (per spec — no naive fixed-character splitting):
  - HEADING and TABLE blocks are never split mid-block if they fit within
    max size alone; a table is kept intact even if that means a chunk runs
    over the target size (splitting a table mid-row destroys its meaning).
  - Paragraphs are packed greedily into a chunk up to chunk_size (estimated
    tokens); a paragraph that alone exceeds chunk_size is split at sentence
    boundaries (never mid-sentence).
  - A heading always starts a new chunk if the current chunk already has
    content — this keeps a chunk's citation "section" accurate rather than
    letting one chunk straddle two sections.
  - Configurable overlap: the tail of each chunk (by estimated tokens) is
    repeated at the start of the next chunk, so retrieval doesn't lose
    context at a chunk boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.chunking.token_estimate import estimate_tokens
from app.services.extraction.schemas import ExtractedDocument, SectionKind

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u0964])\s+")  # \u0964 = Devanagari danda (।)


@dataclass
class Chunk:
    text: str
    page_number: int | None
    section_title: str | None
    token_count: int


def _split_long_paragraph(text: str, max_tokens: int) -> list[str]:
    """Splits a single paragraph that's too big to fit in one chunk, at
    sentence boundaries, never mid-sentence."""
    sentences = _SENTENCE_SPLIT_RE.split(text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if estimate_tokens(candidate) > max_tokens and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _take_overlap_tail(text: str, overlap_tokens: int) -> str:
    """Returns roughly the last `overlap_tokens` worth of text, cut at a
    sentence boundary where possible so overlap reads naturally."""
    if overlap_tokens <= 0:
        return ""
    sentences = _SENTENCE_SPLIT_RE.split(text)
    tail = ""
    for sentence in reversed(sentences):
        candidate = f"{sentence} {tail}".strip() if tail else sentence
        if estimate_tokens(candidate) > overlap_tokens and tail:
            break
        tail = candidate
    return tail


def chunk_document(
    document: ExtractedDocument, *, chunk_size_tokens: int = 512, overlap_tokens: int = 64
) -> list[Chunk]:
    chunks: list[Chunk] = []

    current_text_parts: list[str] = []
    current_tokens = 0
    current_page: int | None = None
    current_section: str | None = None

    def flush():
        nonlocal current_text_parts, current_tokens, current_page, current_section
        if not current_text_parts:
            return
        text = "\n\n".join(current_text_parts)
        chunks.append(
            Chunk(text=text, page_number=current_page, section_title=current_section, token_count=estimate_tokens(text))
        )
        overlap_text = _take_overlap_tail(text, overlap_tokens)
        current_text_parts = [overlap_text] if overlap_text else []
        current_tokens = estimate_tokens(overlap_text)

    for block in document.all_blocks():
        block_tokens = estimate_tokens(block.text)

        # IMPORTANT: check the heading-forces-flush condition using the
        # section/page state as it was BEFORE this block, so the chunk
        # being flushed keeps the section title it actually belongs to.
        # Only after flushing do we adopt this block's page/section as the
        # new "current" state for whatever comes next.
        if block.kind == SectionKind.HEADING and current_text_parts:
            flush()

        current_page = block.page_number if block.page_number is not None else current_page
        current_section = block.section_title if block.section_title is not None else current_section

        if block.kind == SectionKind.TABLE:
            if current_text_parts:
                flush()
            current_text_parts.append(block.text)
            current_tokens += block_tokens
            # A table is always its own chunk boundary after being added —
            # don't let unrelated paragraphs get glued onto it.
            flush()
            continue

        if block_tokens > chunk_size_tokens:
            # Oversized single paragraph: flush what we have, then split
            # this block at sentence boundaries into its own chunk(s).
            flush()
            for piece in _split_long_paragraph(block.text, chunk_size_tokens):
                chunks.append(
                    Chunk(
                        text=piece, page_number=current_page, section_title=current_section,
                        token_count=estimate_tokens(piece),
                    )
                )
            continue

        if current_tokens + block_tokens > chunk_size_tokens and current_text_parts:
            flush()

        current_text_parts.append(block.text)
        current_tokens += block_tokens

    flush()
    return [c for c in chunks if c.text.strip()]
