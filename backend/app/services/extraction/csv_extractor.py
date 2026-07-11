"""CSV extraction. Rendered as a single table block, mirroring the XLSX
extractor's approach, so tabular chunking rules apply uniformly."""

from __future__ import annotations

import csv

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_MAX_ROWS = 10000


class CSVExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        rows_text: list[str] = []
        try:
            with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                # Sniff the dialect (comma vs semicolon vs tab) rather than
                # assuming comma — common in exports from non-US locales.
                sample = f.read(8192)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    dialect = csv.excel
                reader = csv.reader(f, dialect)
                for i, row in enumerate(reader):
                    if i >= _MAX_ROWS:
                        rows_text.append(f"... (truncated after {_MAX_ROWS} rows)")
                        break
                    if any(cell.strip() for cell in row):
                        rows_text.append(" | ".join(row))
        except OSError as e:
            raise ExtractionError(f"Could not read CSV: {e}") from e

        blocks = [ExtractedBlock(kind=SectionKind.TABLE, text="\n".join(rows_text))] if rows_text else []
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
