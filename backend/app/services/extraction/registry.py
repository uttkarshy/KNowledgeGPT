"""
Extractor registry — the single place that maps FileType to a TextExtractor.
Mirrors the LLM provider factory pattern: callers ask for an extractor by
FileType and never import a specific extractor class directly.

Coverage honesty check (as of this increment):

  Fully implemented and tested against real generated files:
    PDF (native text + automatic per-page OCR fallback for scanned pages),
    DOCX, PPTX, XLSX, CSV, TXT, Markdown, HTML, JSON, Images (OCR)

  Implemented but only lightly exercised (no dedicated real-file test in
  this increment — logic is straightforward but unverified end-to-end):
    XML, RTF

  Not implemented — legacy/binary formats needing a system-level converter
  this sandbox can't install and verify (e.g. LibreOffice headless for
  .doc, xlrd for legacy .xls). Raises UnsupportedFormatError with a clear
  message rather than silently mis-extracting:
    DOC (pre-2007 binary Word), XLS (pre-2007 binary Excel), ZIP (nested
    archive — needs a decision on whether contents become one document or
    many; deferred rather than guessed at)
"""

from __future__ import annotations

from app.models.enums import FileType
from app.services.extraction.base import TextExtractor
from app.services.extraction.csv_extractor import CSVExtractor
from app.services.extraction.docx_extractor import DOCXExtractor
from app.services.extraction.html_extractor import HTMLExtractor
from app.services.extraction.image_extractor import ImageExtractor
from app.services.extraction.json_extractor import JSONExtractor
from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.extraction.pptx_extractor import PPTXExtractor
from app.services.extraction.rtf_extractor import RTFExtractor
from app.services.extraction.schemas import UnsupportedFormatError
from app.services.extraction.text_markdown_extractor import TextMarkdownExtractor
from app.services.extraction.xlsx_extractor import XLSXExtractor
from app.services.extraction.xml_extractor import XMLExtractor

_REGISTRY: dict[FileType, TextExtractor] = {
    FileType.PDF: PDFExtractor(),
    FileType.DOCX: DOCXExtractor(),
    FileType.PPTX: PPTXExtractor(),
    FileType.XLSX: XLSXExtractor(),
    FileType.CSV: CSVExtractor(),
    FileType.TXT: TextMarkdownExtractor(is_markdown=False),
    FileType.MARKDOWN: TextMarkdownExtractor(is_markdown=True),
    FileType.HTML: HTMLExtractor(),
    FileType.JSON: JSONExtractor(),
    FileType.XML: XMLExtractor(),
    FileType.RTF: RTFExtractor(),
    FileType.IMAGE: ImageExtractor(),
}

_UNSUPPORTED_MESSAGES: dict[FileType, str] = {
    FileType.DOC: (
        "Legacy .doc (pre-2007 binary Word) extraction requires a system "
        "converter such as LibreOffice headless (`soffice --headless "
        "--convert-to docx`) or antiword. Not wired up in this increment — "
        "recommend converting to .docx at upload time or adding a "
        "LibreOffice-based extractor as a follow-up."
    ),
    FileType.XLS: (
        "Legacy .xls (pre-2007 binary Excel) requires xlrd (openpyxl does "
        "not read this format). Not wired up in this increment."
    ),
    FileType.ZIP: (
        "ZIP archive extraction is deferred pending a product decision: "
        "should each file inside become its own Document (separate "
        "citations, separate chunks) or be concatenated into one? Wire up "
        "once that's decided — the mechanics (unzip to temp dir, recurse "
        "this same registry per contained file) are straightforward."
    ),
}


def get_extractor(file_type: FileType) -> TextExtractor:
    extractor = _REGISTRY.get(file_type)
    if extractor is None:
        message = _UNSUPPORTED_MESSAGES.get(
            file_type, f"No extractor registered for file type '{file_type.value}'"
        )
        raise UnsupportedFormatError(message)
    return extractor
