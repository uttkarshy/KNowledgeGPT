"""CSV row provenance where headers are recognizable; preserve other layouts."""

from __future__ import annotations

import csv
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

_MAX_ROWS = 10000


class CSVExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        rows_text = []
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
                        raise ExtractionError(f"CSV exceeds {_MAX_ROWS} rows; split the file before uploading")
                    if any(cell.strip() for cell in row):
                        rows_text.append(row)
        except OSError as e:
            raise ExtractionError(f"Could not read CSV: {e}") from e

        from app.services.extraction.table_rows import row_block

        headers_known = rows_text and any(
            re.fullmatch(
                r"name|date|transaction date|description|account(?: no\.?)?|ifsc(?: code)?|net payable|debit|credit|amount",
                h.strip(),
                re.I,
            )
            for h in rows_text[0]
        )
        if headers_known:
            blocks = [
                row_block(rows_text[0], row, page_number=1, table_id=0, row_index=i)
                for i, row in enumerate(rows_text[1:], 1)
            ]
        else:
            blocks = (
                [ExtractedBlock(SectionKind.TABLE, "\n".join(" | ".join(row) for row in rows_text), page_number=1)]
                if rows_text
                else []
            )
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
