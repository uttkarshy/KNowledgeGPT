"""Explicit row provenance. Never infer unknown cells or merge distinct rows."""

from app.services.extraction.schemas import ExtractedBlock, SectionKind


def row_block(headers, values, *, page_number, table_id, row_index, confidence=None, rotation=0):
    headers = list(headers) + [None] * max(0, len(values) - len(headers))
    headers = [str(h or f"Column {i + 1}").strip() for i, h in enumerate(headers)]
    headers = [h if headers.count(h) == 1 else f"{h} ({i + 1})" for i, h in enumerate(headers)]
    cells = {
        h: str(values[i]).strip() if i < len(values) and values[i] is not None else "" for i, h in enumerate(headers)
    }
    # Repeated header plus pipe row retains compatibility with the exact-date path.
    text = " | ".join(headers) + "\n" + " | ".join(cells.values())
    return ExtractedBlock(
        kind=SectionKind.TABLE,
        text=text,
        page_number=page_number,
        structure={
            "kind": "table_row",
            "table_id": table_id,
            "row_index": row_index,
            "cells": cells,
            "confidence": confidence,
            "rotation": rotation,
        },
    )
