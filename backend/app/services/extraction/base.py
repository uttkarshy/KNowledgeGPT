"""
TextExtractor — the interface every format-specific extractor implements.
Mirrors the LLMProvider pattern: the chunker and embedding pipeline depend
only on this interface and on app.services.extraction.schemas, never on a
specific extractor or its underlying library (fitz, python-docx, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import Settings
from app.services.extraction.schemas import ExtractedDocument


class TextExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        raise NotImplementedError
