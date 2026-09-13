"""
PDF extraction via PyMuPDF (fitz).

Automatically detects scanned pages: if a page's embedded text layer is
empty or suspiciously short relative to its content, the page is rasterized
and run through Tesseract OCR instead. This means a single PDF can be
partly-native-text and partly-scanned (common with mixed reports) and each
page is handled correctly.
"""

from __future__ import annotations

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
from app.services.ocr.tesseract_engine import detect_script_language, ocr_image

_MIN_CHARS_PER_PAGE_TO_SKIP_OCR = 20  # below this, treat the page as scanned
_OCR_RENDER_DPI_ZOOM = 2.0  # ~144 DPI, good balance of OCR accuracy vs. speed


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
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            doc = fitz.open(file_path)
        except Exception as e:  # PyMuPDF raises its own RuntimeError/fitz errors
            raise ExtractionError(f"Could not open PDF: {e}") from e

        pages: list[ExtractedPage] = []
        if doc.is_encrypted or len(doc) > settings.MAX_PDF_PAGES:
            doc.close()
            raise ExtractionError("PDF is encrypted or exceeds the page limit")
        current_section_title: str | None = None
        lang_votes: dict[str, int] = {}

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_number = page_index + 1
            native_text = page.get_text("text").strip()

            if len(native_text) >= _MIN_CHARS_PER_PAGE_TO_SKIP_OCR:
                blocks, current_section_title = self._extract_native_blocks(
                    page, page_number, current_section_title
                )
                pages.append(ExtractedPage(page_number=page_number, blocks=blocks, was_ocr=False))
                lang_votes["native"] = lang_votes.get("native", 0) + 1
            else:
                if page.rect.width * page.rect.height * _OCR_RENDER_DPI_ZOOM**2 > 30_000_000:
                    raise ExtractionError("PDF page exceeds the safe OCR pixel limit")
                pix = page.get_pixmap(matrix=fitz.Matrix(_OCR_RENDER_DPI_ZOOM, _OCR_RENDER_DPI_ZOOM))
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                eng_result = ocr_image(image, languages=["eng"])
                hin_result = ocr_image(image, languages=["hin"])
                page_lang = detect_script_language(eng_result, hin_result)
                best = eng_result if page_lang != "hi" else hin_result
                if page_lang == "en+hi":
                    combined = ocr_image(image, languages=["eng", "hin"])
                    best = combined

                block = ExtractedBlock(
                    kind=SectionKind.PARAGRAPH,
                    text=best.text,
                    page_number=page_number,
                    section_title=current_section_title,
                )
                pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        blocks=[block] if best.text else [],
                        was_ocr=True,
                        ocr_confidence=best.mean_confidence,
                    )
                )
                lang_votes[page_lang] = lang_votes.get(page_lang, 0) + 1

        doc.close()

        detected_language = None
        non_native_votes = {k: v for k, v in lang_votes.items() if k != "native"}
        if non_native_votes:
            detected_language = max(non_native_votes, key=non_native_votes.get)

        return ExtractedDocument(pages=pages, detected_language=detected_language, page_count=len(pages))

    def _extract_native_blocks(
        self, page: "fitz.Page", page_number: int, current_section_title: str | None
    ) -> tuple[list[ExtractedBlock], str | None]:
        blocks: list[ExtractedBlock] = []
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
