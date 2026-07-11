"""Plain text and Markdown extraction. Markdown `#`-style headings are
detected and preserved as heading blocks; plain .txt is split into
paragraphs on blank lines with no heading structure (there is none to find)."""

from __future__ import annotations

import re

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_MD_LIST_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+(.*)")


class TextMarkdownExtractor(TextExtractor):
    def __init__(self, *, is_markdown: bool):
        self._is_markdown = is_markdown

    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError as e:
            raise ExtractionError(f"Could not read text file: {e}") from e

        blocks: list[ExtractedBlock] = []
        current_section_title: str | None = None

        if self._is_markdown:
            for line in raw.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                heading_match = _MD_HEADING_RE.match(stripped)
                list_match = _MD_LIST_RE.match(stripped)
                if heading_match:
                    level = len(heading_match.group(1))
                    text = heading_match.group(2).strip()
                    current_section_title = text
                    blocks.append(
                        ExtractedBlock(kind=SectionKind.HEADING, text=text, heading_level=level, section_title=current_section_title)
                    )
                elif list_match:
                    blocks.append(
                        ExtractedBlock(kind=SectionKind.LIST_ITEM, text=list_match.group(2).strip(), section_title=current_section_title)
                    )
                else:
                    blocks.append(
                        ExtractedBlock(kind=SectionKind.PARAGRAPH, text=stripped, section_title=current_section_title)
                    )
        else:
            for para in re.split(r"\n\s*\n", raw):
                para = para.strip()
                if para:
                    blocks.append(ExtractedBlock(kind=SectionKind.PARAGRAPH, text=para))

        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
