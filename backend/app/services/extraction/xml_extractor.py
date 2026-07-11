"""XML extraction via lxml. Best-effort: extracts text content of every leaf
element, prefixed with its tag name, since arbitrary XML has no universal
notion of "heading" or "paragraph" the way HTML/DOCX do."""

from __future__ import annotations

from lxml import etree

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_MAX_ELEMENTS = 5000


class XMLExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            tree = etree.parse(file_path)
        except etree.XMLSyntaxError as e:
            raise ExtractionError(f"Could not parse XML: {e}") from e

        lines: list[str] = []
        for element in tree.iter():
            if len(lines) >= _MAX_ELEMENTS:
                lines.append(f"... (truncated after {_MAX_ELEMENTS} elements)")
                break
            text = (element.text or "").strip()
            if text:
                tag = etree.QName(element).localname
                lines.append(f"{tag}: {text}")

        blocks = [
            ExtractedBlock(kind=SectionKind.PARAGRAPH, text="\n".join(lines[i : i + 50]))
            for i in range(0, len(lines), 50)
        ]
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
