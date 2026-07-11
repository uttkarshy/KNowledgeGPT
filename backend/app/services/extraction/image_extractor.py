"""Standalone image extraction (PNG/JPG/TIFF/BMP uploaded directly, not
embedded in a PDF). Runs the same English+Hindi OCR path as the PDF
extractor's scanned-page fallback."""

from __future__ import annotations

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


class ImageExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            image = Image.open(file_path).convert("RGB")
        except Exception as e:
            raise ExtractionError(f"Could not open image: {e}") from e

        eng_result = ocr_image(image, languages=["eng"])
        hin_result = ocr_image(image, languages=["hin"])
        detected_language = detect_script_language(eng_result, hin_result)

        best = eng_result
        if detected_language == "hi":
            best = hin_result
        elif detected_language == "en+hi":
            best = ocr_image(image, languages=["eng", "hin"])

        blocks = [ExtractedBlock(kind=SectionKind.PARAGRAPH, text=best.text)] if best.text else []
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=True, ocr_confidence=best.mean_confidence)
        return ExtractedDocument(pages=[page], detected_language=detected_language, page_count=1)
