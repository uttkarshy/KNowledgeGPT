"""
PDF extraction via PyMuPDF (fitz).

Automatically detects scanned pages: if a page's embedded text layer is
empty or suspiciously short relative to its content, the page is rasterized
and run through Tesseract OCR instead. This means a single PDF can be
partly-native-text and partly-scanned (common with mixed reports) and each
page is handled correctly.
"""

from __future__ import annotations

from contextlib import contextmanager
import re
import signal
import threading
import time

import fitz  # PyMuPDF
from PIL import Image

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)
from app.services.extraction.table_rows import row_block
from app.services.ocr.structured import scanned_page
from app.services.processing_errors import ProcessingFailure

_MIN_CHARS_PER_PAGE_TO_SKIP_OCR = 20  # below this, treat the page as scanned
_OCR_RENDER_DPI_ZOOM = 3.0  # ~216 DPI, good balance of OCR accuracy vs. speed
_TABLE_EXTRACTION_TIMEOUT_SECONDS = 30


class _TableExtractionTimedOut(Exception):
    pass


@contextmanager
def _table_extraction_deadline(seconds: float):
    """Interrupt PyMuPDF table discovery before it can monopolize a worker.

    Celery's production prefork child runs the task on its main thread on
    Linux, where an interval timer can interrupt PyMuPDF's Python table
    analysis. Keep a no-op fallback for non-POSIX/unit-test callers; the
    Celery task's hard time limit remains the final process-level guard.
    """
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        yield
        return

    started = time.monotonic()
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_delay, previous_interval = signal.getitimer(signal.ITIMER_REAL)

    def _raise_timeout(_signum, _frame):
        raise _TableExtractionTimedOut

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_delay > 0:
            remaining = max(0.001, previous_delay - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_interval)


def _heading_level_for_span(span_size: float, body_size: float) -> int | None:
    """Heuristic: a text span notably larger than the page's modal font
    size is treated as a heading. PDFs have no semantic heading tags, so
    font-size-relative-to-body is the standard practical proxy."""
    if span_size >= body_size * 1.6:
        return 1
    if span_size >= body_size * 1.3:
        return 2
    return None


class PDFExtractor(TextExtractor):
    def page_count(self, file_path: str, *, settings: Settings) -> int:
        try:
            with fitz.open(file_path) as doc:
                if doc.is_encrypted:
                    raise ProcessingFailure("encrypted_pdf", "This PDF is encrypted. Upload an unlocked copy.")
                count = len(doc)
        except ProcessingFailure:
            raise
        except Exception as e:
            raise ExtractionError(f"Could not open PDF: {e}") from e
        if count > settings.MAX_PDF_PAGES:
            raise ProcessingFailure(
                "page_limit_exceeded",
                f"This PDF contains {count} pages. KnowledgeGPT supports up to {settings.MAX_PDF_PAGES} pages per document.",
            )
        return count

    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        count = self.page_count(file_path, settings=settings)
        return self.extract_range(file_path, settings=settings, start_page=1, end_page=count)

    def extract_range(
        self, file_path: str, *, settings: Settings, start_page: int, end_page: int
    ) -> ExtractedDocument:
        try:
            doc = fitz.open(file_path)
        except Exception as e:  # PyMuPDF raises its own RuntimeError/fitz errors
            raise ExtractionError(f"Could not open PDF: {e}") from e

        pages: list[ExtractedPage] = []
        if doc.is_encrypted:
            doc.close()
            raise ProcessingFailure("encrypted_pdf", "This PDF is encrypted. Upload an unlocked copy.")
        total_pages = len(doc)
        if total_pages > settings.MAX_PDF_PAGES:
            doc.close()
            raise ProcessingFailure("page_limit_exceeded", f"This PDF contains {total_pages} pages. KnowledgeGPT supports up to {settings.MAX_PDF_PAGES} pages per document.")
        start_page = max(1, start_page)
        end_page = min(total_pages, end_page)
        current_section_title: str | None = None

        try:
            for page_index in range(start_page - 1, end_page):
                page = doc[page_index]
                page_number = page_index + 1
                native_text = page.get_text("text").strip()

                image_area = max((fitz.Rect(info["bbox"]).get_area() for info in page.get_image_info()), default=0)
                scanned = len(native_text) < _MIN_CHARS_PER_PAGE_TO_SKIP_OCR or (
                    len(native_text) < 100 and image_area > page.rect.get_area() * 0.5
                )
                if not scanned:
                    blocks, current_section_title = self._extract_native_blocks(
                        page, page_number, current_section_title
                    )
                    pages.append(ExtractedPage(page_number=page_number, blocks=blocks, was_ocr=False))
                else:
                    if page.rect.width * page.rect.height * _OCR_RENDER_DPI_ZOOM**2 > 12_000_000:
                        raise ProcessingFailure(
                            "ocr_failure", "PDF page exceeds the safe OCR resolution. Upload a smaller scan."
                        )
                    pix = page.get_pixmap(matrix=fitz.Matrix(_OCR_RENDER_DPI_ZOOM, _OCR_RENDER_DPI_ZOOM))
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                    try:
                        pages.append(scanned_page(image, page_number))
                    finally:
                        image.close()

        finally:
            doc.close()

        return ExtractedDocument(pages=pages, detected_language=None, page_count=total_pages)

    def _extract_native_blocks(
        self, page: "fitz.Page", page_number: int, current_section_title: str | None
    ) -> tuple[list[ExtractedBlock], str | None]:
        blocks: list[ExtractedBlock] = []
        bounds = []
        try:
            with _table_extraction_deadline(_TABLE_EXTRACTION_TIMEOUT_SECONDS):
                tables = page.find_tables().tables
        except _TableExtractionTimedOut as exc:
            raise ProcessingFailure(
                "processing_timeout",
                "PDF table extraction exceeded the time budget. Retry Processing or upload a simplified PDF.",
                retryable=True,
            ) from exc
        for table_id, table in enumerate(tables):
            rows = table.extract()
            if len(rows) < 2:
                continue
            # Reject missing headers instead of assigning invented column names.
            if not any(re.search(r"[A-Za-z]", str(v or "")) for v in rows[0]):
                continue
            bounds.append(fitz.Rect(table.bbox))
            for row_index, values in enumerate(rows[1:], 1):
                blocks.append(
                    row_block(rows[0], values, page_number=page_number, table_id=table_id, row_index=row_index)
                )
        page_dict = page.get_text("dict")

        # Determine the modal (most common) font size on the page as the
        # "body text" baseline for the heading heuristic.
        sizes: list[float] = []
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(round(span["size"]))
        body_size = max(set(sizes), key=sizes.count) if sizes else 10.0

        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                if any(bound.contains(fitz.Rect(line["bbox"])) for bound in bounds):
                    continue
                line_text = "".join(span["text"] for span in line.get("spans", [])).strip()
                if not line_text:
                    continue
                max_span_size = max((span["size"] for span in line.get("spans", [])), default=body_size)
                level = _heading_level_for_span(max_span_size, body_size)

                if level is not None:
                    current_section_title = line_text
                    blocks.append(
                        ExtractedBlock(
                            kind=SectionKind.HEADING,
                            text=line_text,
                            heading_level=level,
                            page_number=page_number,
                            section_title=current_section_title,
                        )
                    )
                else:
                    blocks.append(
                        ExtractedBlock(
                            kind=SectionKind.PARAGRAPH,
                            text=line_text,
                            page_number=page_number,
                            section_title=current_section_title,
                        )
                    )

        return blocks, current_section_title
