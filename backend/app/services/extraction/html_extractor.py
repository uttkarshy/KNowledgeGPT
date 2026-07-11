"""HTML extraction via BeautifulSoup. <h1>-<h6> become heading blocks,
<li> become list items, <table> rows are rendered pipe-delimited. Script/
style/nav/footer content is stripped before extraction."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_HEADING_TAGS = {f"h{i}": i for i in range(1, 7)}
_NOISE_TAGS = ["script", "style", "nav", "footer", "noscript"]


class HTMLExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                soup = BeautifulSoup(f.read(), "lxml")
        except OSError as e:
            raise ExtractionError(f"Could not read HTML: {e}") from e

        for tag in soup(_NOISE_TAGS):
            tag.decompose()

        blocks: list[ExtractedBlock] = []
        current_section_title: str | None = None

        body = soup.body or soup
        for el in body.find_all(list(_HEADING_TAGS) + ["p", "li", "table"]):
            if el.name in _HEADING_TAGS:
                text = el.get_text(strip=True)
                if text:
                    current_section_title = text
                    blocks.append(
                        ExtractedBlock(kind=SectionKind.HEADING, text=text, heading_level=_HEADING_TAGS[el.name], section_title=current_section_title)
                    )
            elif el.name == "li":
                text = el.get_text(strip=True)
                if text:
                    blocks.append(ExtractedBlock(kind=SectionKind.LIST_ITEM, text=text, section_title=current_section_title))
            elif el.name == "table":
                rows = []
                for tr in el.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    blocks.append(ExtractedBlock(kind=SectionKind.TABLE, text="\n".join(rows), section_title=current_section_title))
            else:  # <p>
                text = el.get_text(strip=True)
                if text:
                    blocks.append(ExtractedBlock(kind=SectionKind.PARAGRAPH, text=text, section_title=current_section_title))

        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
