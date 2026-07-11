"""DOCX extraction via python-docx. Preserves heading levels (from Word
paragraph styles), list items, and renders tables as pipe-delimited text
blocks so the chunker can keep them intact rather than splitting mid-row."""

from __future__ import annotations

import docx
from docx.table import Table

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)


def _heading_level_from_style(style_name: str) -> int | None:
    if not style_name:
        return None
    style_name = style_name.lower()
    if style_name.startswith("heading"):
        digits = "".join(ch for ch in style_name if ch.isdigit())
        return int(digits) if digits else 1
    if style_name in ("title",):
        return 1
    return None


def _render_table(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


class DOCXExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            document = docx.Document(file_path)
        except Exception as e:
            raise ExtractionError(f"Could not open DOCX: {e}") from e

        blocks: list[ExtractedBlock] = []
        current_section_title: str | None = None

        # python-docx exposes body children in document order via
        # document.element.body, but iterating paragraphs/tables separately
        # is simpler and preserves reading order well enough for chunking
        # purposes (exact interleaving order matters less than keeping each
        # table/paragraph intact).
        for para in document.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            level = _heading_level_from_style(para.style.name if para.style else "")
            is_list = para.style.name.lower().startswith(("list", "bullet")) if para.style else False

            if level is not None:
                current_section_title = text
                blocks.append(
                    ExtractedBlock(kind=SectionKind.HEADING, text=text, heading_level=level, section_title=current_section_title)
                )
            elif is_list:
                blocks.append(
                    ExtractedBlock(kind=SectionKind.LIST_ITEM, text=text, section_title=current_section_title)
                )
            else:
                blocks.append(
                    ExtractedBlock(kind=SectionKind.PARAGRAPH, text=text, section_title=current_section_title)
                )

        for table in document.tables:
            rendered = _render_table(table)
            if rendered.strip():
                blocks.append(
                    ExtractedBlock(kind=SectionKind.TABLE, text=rendered, section_title=current_section_title)
                )

        # DOCX has no fixed pagination at the file level, so the whole
        # document is modeled as a single logical page. Page numbers in
        # citations for DOCX sources are therefore None — the chunker/
        # citation UI falls back to section titles instead.
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
