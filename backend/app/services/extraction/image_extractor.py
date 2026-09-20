"""Standalone image extraction (PNG/JPG/TIFF/BMP uploaded directly, not
embedded in a PDF). Runs the same English+Hindi OCR path as the PDF
extractor's scanned-page fallback."""

from __future__ import annotations

from PIL import Image

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedDocument,
    ExtractionError,
)


class ImageExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            image = Image.open(file_path).convert("RGB")
        except Exception as e:
            raise ExtractionError(f"Could not open image: {e}") from e

        from app.services.ocr.structured import scanned_page

        try:
            page = scanned_page(image, 1)
            return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
        finally:
            image.close()
