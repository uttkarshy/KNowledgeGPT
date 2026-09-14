"""Spreadsheet extraction. Each worksheet becomes a "page" (page_number =
sheet index), the sheet name becomes the section title, and rows are
rendered as pipe-delimited text. Rows are batched into multiple TABLE
blocks per sheet (rather than one block for the entire sheet) so that
large spreadsheets don't produce a single oversized chunk downstream.

Bug this fixes: a sheet with ~1,100 rows previously became ONE table
block, and the chunker deliberately never splits table blocks (to avoid
breaking a row apart) — so that entire sheet became a single chunk of
tens of thousands of tokens. OpenAI's embedding API hard-rejects any
input over 8,191 tokens, so a spreadsheet of any real size would fail at
the embedding step. Batching here keeps every block (and therefore every
downstream chunk) safely under that ceiling, while still never splitting
a single row's data across two blocks.
"""

from __future__ import annotations

import openpyxl

from app.core.config import Settings
from app.services.chunking.token_estimate import estimate_tokens
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_MAX_ROWS_PER_SHEET = 5000  # guardrail against pathological spreadsheets

# Target token ceiling per TABLE block. Kept well under OpenAI's 8,191
# hard limit for embedding inputs (leaving headroom since our token count
# is an estimate, not exact), and close to the chunker's own default
# chunk_size_tokens (512) so blocks align naturally with chunk boundaries
# instead of the chunker having to further split or awkwardly pack them.
_MAX_TOKENS_PER_BLOCK = 700


def _header_line(header_cells: list[str]) -> str:
    return " | ".join(header_cells)


class XLSXExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        except Exception as e:
            raise ExtractionError(f"Could not open spreadsheet: {e}") from e

        pages: list[ExtractedPage] = []

        try:
            for sheet_index, sheet in enumerate(workbook.worksheets):
                sheet_number = sheet_index + 1
                blocks: list[ExtractedBlock] = [
                    ExtractedBlock(
                        kind=SectionKind.HEADING, text=sheet.title, heading_level=1,
                        page_number=sheet_number, section_title=sheet.title,
                    )
                ]

                header_cells: list[str] | None = None
                header_tokens = 0
                current_rows: list[str] = []
                current_tokens = 0

                def flush_block(rows, header, output, page_number, title):
                    if not rows:
                        return
                    # Repeat the header in every block so each chunk is
                    # independently interpretable by the LLM at retrieval
                    # time — a block of bare data rows with no column names
                    # is far less useful than one that carries them.
                    text_parts = [_header_line(header)] if header else []
                    text_parts.extend(rows)
                    output.append(
                        ExtractedBlock(
                            kind=SectionKind.TABLE, text="\n".join(text_parts),
                            page_number=page_number, section_title=title,
                        )
                    )

                for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
                    if row_index >= _MAX_ROWS_PER_SHEET:
                        raise ExtractionError(f"Spreadsheet exceeds {_MAX_ROWS_PER_SHEET} rows per sheet; split the file before uploading")

                    cells = ["" if v is None else str(v) for v in row]
                    if not any(c.strip() for c in cells):
                        continue

                    if header_cells is None:
                        header_cells = cells
                        header_tokens = estimate_tokens(_header_line(header_cells))
                        continue

                    row_line = " | ".join(cells)
                    row_tokens = estimate_tokens(row_line)

                    if current_rows and (current_tokens + row_tokens + header_tokens > _MAX_TOKENS_PER_BLOCK):
                        flush_block(current_rows, header_cells, blocks, sheet_number, sheet.title)
                        current_rows = []
                        current_tokens = 0

                    current_rows.append(row_line)
                    current_tokens += row_tokens

                flush_block(current_rows, header_cells, blocks, sheet_number, sheet.title)
                pages.append(ExtractedPage(page_number=sheet_number, blocks=blocks, was_ocr=False))

        finally:
            workbook.close()
        return ExtractedDocument(pages=pages, detected_language=None, page_count=len(pages))
