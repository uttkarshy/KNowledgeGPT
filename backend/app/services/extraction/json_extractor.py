"""JSON extraction. Flattens arbitrarily nested structures into
"dotted.path: value" lines grouped into blocks, so the semantic content is
searchable/embeddable rather than treating the file as an opaque blob."""

from __future__ import annotations

import json

from app.core.config import Settings
from app.services.extraction.base import TextExtractor
from app.services.extraction.schemas import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionError,
    SectionKind,
)

_MAX_LINES = 5000


def _flatten(obj, prefix: str, lines: list[str]) -> None:
    if len(lines) >= _MAX_LINES:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            _flatten(value, f"{prefix}.{key}" if prefix else str(key), lines)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _flatten(item, f"{prefix}[{i}]", lines)
    else:
        lines.append(f"{prefix}: {obj}")


class JSONExtractor(TextExtractor):
    def extract(self, file_path: str, *, settings: Settings) -> ExtractedDocument:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ExtractionError(f"Could not parse JSON: {e}") from e

        lines: list[str] = []
        _flatten(data, "", lines)
        if len(lines) >= _MAX_LINES:
            lines.append(f"... (truncated after {_MAX_LINES} fields)")

        # Grouped into chunks of 50 key/value lines per block so the
        # chunker isn't forced to treat an entire huge JSON file as one
        # giant unsplittable table.
        blocks = [
            ExtractedBlock(kind=SectionKind.TABLE, text="\n".join(lines[i : i + 50]))
            for i in range(0, len(lines), 50)
        ]
        page = ExtractedPage(page_number=1, blocks=blocks, was_ocr=False)
        return ExtractedDocument(pages=[page], detected_language=None, page_count=1)
