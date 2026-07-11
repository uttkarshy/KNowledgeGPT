"""Spreadsheet extraction. Each worksheet becomes a "page" (page_number =
sheet index), the sheet name becomes the section title, and rows are
rendered as pipe-delimited text so the chunker treats each sheet's data as
a table block rather than splitting rows apart mid-record."""

from __future__ import annotations

import openpyxl

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_MAX_ROWS_PER_SHEET = 5000  # guardrail against pathological spreadsheets


class XLSXExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        except Exception as e:
            raise ExtractionError(f"Could not open spreadsheet: {e}") from e

        pages: list[ExtractedPage] = []

        for sheet_index, sheet in enumerate(workbook.worksheets):
            sheet_number = sheet_index + 1
            rows_text: list[str] = []

            for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_index >= _MAX_ROWS_PER_SHEET:
                    rows_text.append(f"... (truncated after {_MAX_ROWS_PER_SHEET} rows)")
                    break
                cells = ["" if v is None else str(v) for v in row]
                if any(c.strip() for c in cells):
                    rows_text.append(" | ".join(cells))

            blocks: list[ExtractedBlock] = [
                ExtractedBlock(
                    kind=SectionKind.HEADING, text=sheet.title, heading_level=1,
                    page_number=sheet_number, section_title=sheet.title,
                )
            ]
            if rows_text:
                blocks.append(
                    ExtractedBlock(
                        kind=SectionKind.TABLE, text="\n".join(rows_text),
                        page_number=sheet_number, section_title=sheet.title,
                    )
                )

            pages.append(ExtractedPage(page_number=sheet_number, blocks=blocks, was_ocr=False))

        workbook.close()
        return ExtractedDocument(pages=pages, detected_language=None, page_count=len(pages))
