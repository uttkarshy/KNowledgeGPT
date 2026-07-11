"""
Tesseract OCR wrapper.

Handles English, Hindi, and mixed English+Hindi documents (Tesseract
supports multi-language recognition natively via `+`-joined lang codes,
e.g. "eng+hin", rather than needing separate passes).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytesseract
from PIL import Image


@dataclass
class OCRResult:
    text: str
    mean_confidence: float  # 0-100, -1 entries (no confidence) excluded from the mean


def ocr_image(image: Image.Image, *, languages: list[str] | None = None) -> OCRResult:
    """Runs Tesseract on a single image. `languages` uses Tesseract's ISO
    639-2 codes (e.g. ["eng"], ["hin"], ["eng", "hin"] for mixed documents).
    Defaults to English+Hindi since that's this platform's specified scope.
    """
    langs = languages or ["eng", "hin"]
    lang_str = "+".join(langs)

    text = pytesseract.image_to_string(image, lang=lang_str)

    data = pytesseract.image_to_data(image, lang=lang_str, output_type=pytesseract.Output.DICT)
    confidences = [float(c) for c in data.get("conf", []) if c not in ("-1", -1)]
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return OCRResult(text=text.strip(), mean_confidence=mean_confidence)


def detect_script_language(ocr_result_eng: OCRResult, ocr_result_hin: OCRResult) -> str:
    """Cheap heuristic: whichever language pass got higher mean confidence
    and produced more text is treated as dominant. Genuinely mixed
    documents (both passes strong) are labeled 'en+hi'. This is a
    heuristic, not true language identification — good enough to tag
    metadata, not to be relied on for anything precision-critical.
    """
    eng_score = ocr_result_eng.mean_confidence * len(ocr_result_eng.text)
    hin_score = ocr_result_hin.mean_confidence * len(ocr_result_hin.text)

    if eng_score == 0 and hin_score == 0:
        return "en"
    ratio = eng_score / (hin_score + 1e-9)
    if 0.4 < ratio < 2.5:
        return "en+hi"
    return "en" if eng_score > hin_score else "hi"
