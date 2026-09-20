"""Evaluate private scan files locally; stdout contains aggregate metrics, never text.

Usage: PYTHONPATH=backend python scripts/evaluate_scans.py /private/one.pdf ...
Do not commit the supplied PDFs or extracted text. This performs real CPU OCR,
not an ingestion/provider/database acceptance test.
"""

import json
import sys
import time

import fitz
from app.services.chunking.semantic_chunker import bound_chunk_bytes, chunk_document
from app.services.extraction.schemas import ExtractedDocument
from app.services.ocr.structured import scanned_page
from app.services.processing_errors import ProcessingFailure
from PIL import Image

for filename in sys.argv[1:]:
    start = time.monotonic()
    pages = []
    errors = []
    with fitz.open(filename) as doc:
        for index in range(len(doc)):
            try:
                pix = doc[index].get_pixmap(matrix=fitz.Matrix(3, 3))
                with Image.frombytes(
                    "RGB", (pix.width, pix.height), pix.samples
                ) as image:
                    page = scanned_page(image, index + 1)
                pages.append(page)
                rows = [
                    b
                    for b in page.blocks
                    if b.structure and b.structure.get("kind") == "table_row"
                ]
                print(
                    json.dumps(
                        {
                            "page": index + 1,
                            "rows": len(rows),
                            "blocks": len(page.blocks),
                            "rotation": next(
                                (
                                    b.structure.get("rotation")
                                    for b in page.blocks
                                    if b.structure
                                ),
                                None,
                            ),
                        }
                    ),
                    flush=True,
                )
            except ProcessingFailure as exc:
                errors.append({"page": index + 1, "error_code": exc.code})
    blocks = [b for page in pages for b in page.blocks]
    named_rows = {
        name: [
            b
            for b in blocks
            if b.structure
            and b.structure.get("kind") == "table_row"
            and name in b.text.lower()
        ]
        for name in ("shravan kumar", "suneel singh")
    }
    lookup = {
        name: {
            "matched_rows": len(rows),
            "pages": sorted({r.page_number for r in rows}),
            "all_requested_columns_nonempty": all(
                all(
                    any(
                        term in k.lower() and str(v).strip()
                        for k, v in r.structure["cells"].items()
                    )
                    for term in ("account", "ifsc", "payable")
                )
                for r in rows
            )
            if rows
            else False,
        }
        for name, rows in named_rows.items()
    }
    try:
        chunks = bound_chunk_bytes(
            chunk_document(ExtractedDocument(pages=pages, page_count=len(pages))), 1800
        )
        chunk_result = {
            "chunks": len(chunks),
            "within_default_chunk_limit": len(chunks) <= 1000,
        }
    except ProcessingFailure as exc:
        chunk_result = {"chunking_error": exc.code}
    print(
        json.dumps(
            {
                "fixture": filename.rsplit("/", 1)[-1],
                "pages_extracted": len(pages),
                "errors": errors,
                "elapsed_seconds": round(time.monotonic() - start),
                "requested_row_checks": lookup,
                **chunk_result,
            }
        ),
        flush=True,
    )
