"""
Provider-agnostic extraction contracts. Every extractor (PDF, DOCX, PPTX,
...) and every consumer (the chunker) speaks only in these types — mirrors
the same pattern as app.schemas.llm for the LLM provider layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SectionKind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"


@dataclass
class ExtractedBlock:
    """One structural unit of a document — a heading, a paragraph, a table
    rendered as text, or a list item. The chunker respects these boundaries
    rather than blindly splitting by character count."""

    kind: SectionKind
    text: str
    heading_level: int | None = None   # 1 = H1/Title, 2 = H2, etc. Only set for HEADING blocks.
    page_number: int | None = None
    section_title: str | None = None   # nearest enclosing heading, for citation display
    structure: dict | None = None


@dataclass
class ExtractedPage:
    page_number: int
    blocks: list[ExtractedBlock] = field(default_factory=list)
    was_ocr: bool = False               # True if this page had no text layer and OCR was used
    ocr_confidence: float | None = None  # mean OCR confidence, if OCR was used


@dataclass
class ExtractedDocument:
    pages: list[ExtractedPage] = field(default_factory=list)
    detected_language: str | None = None  # e.g. "en", "hi", "en+hi"
    page_count: int = 0

    def all_blocks(self) -> list[ExtractedBlock]:
        return [block for page in self.pages for block in page.blocks]


class ExtractionError(Exception):
    pass


class UnsupportedFormatError(ExtractionError):
    """Raised by extractors that are intentionally not fully implemented yet
    (see registry.py docstring for current coverage)."""
