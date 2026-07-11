"""RTF extraction via striprtf. This library strips formatting to plain
text; it does not preserve heading semantics (RTF's heading styles aren't
reliably exposed by this lightweight parser), so RTF documents are treated
as a flat sequence of paragraphs, same as plain .txt."""

from __future__ import annotations

import re

from striprtf.striprtf import rtf_to_text

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)


class RTFExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_rtf = f.read()
            plain_text = rtf_to_text(raw_rtf)
        except Exception as e:
            raise ExtractionError(f"Could not parse RTF: {e}") from e

        blocks = [
            ExtractedBlock(kind=SectionKind.PARAGRAPH, text=para.strip())
            for para in re.split(r"\n\s*\n", plain_text)
            if para.strip()
        ]
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
