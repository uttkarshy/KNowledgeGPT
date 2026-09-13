"""
Regression tests for two bugs found while processing a real ~1,100-row
spreadsheet:

1. XLSXExtractor used to render an entire sheet as ONE table block,
   producing a single chunk of tens of thousands of tokens for any
   sizeable spreadsheet - far over OpenAI's 8,191-token embedding input
   limit, so embedding would fail for any real-world-sized spreadsheet.

2. The chunker's overlap logic silently returned the ENTIRE previous
   chunk's text (instead of a short tail) whenever that text had no
   sentence-ending punctuation - true of every pipe-delimited table row -
   causing chunk sizes to snowball across any long run of table blocks.
"""

from app.services.chunking.semantic_chunker import _take_overlap_tail, chunk_document
from app.services.extraction.schemas import ExtractedBlock, ExtractedDocument, ExtractedPage, SectionKind


def _make_large_table_document(num_rows: int = 500, num_cols: int = 10) -> ExtractedDocument:
    """Simulates what XLSXExtractor now produces for a large sheet: many
    small TABLE blocks rather than one giant one."""
    header = " | ".join(f"col{i}" for i in range(num_cols))
    blocks = [ExtractedBlock(kind=SectionKind.HEADING, text="Sheet1", heading_level=1, section_title="Sheet1")]

    batch = [header]
    for row in range(num_rows):
        batch.append(" | ".join(f"value_{row}_{i}" for i in range(num_cols)))
        if len(batch) >= 30:
            blocks.append(ExtractedBlock(kind=SectionKind.TABLE, text="\n".join(batch), section_title="Sheet1"))
            batch = [header]
    if len(batch) > 1:
        blocks.append(ExtractedBlock(kind=SectionKind.TABLE, text="\n".join(batch), section_title="Sheet1"))

    return ExtractedDocument(pages=[ExtractedPage(page_number=1, blocks=blocks)], page_count=1)


def test_overlap_of_punctuation_free_table_text_is_bounded_not_the_whole_input():
    """The exact bug: pipe-delimited rows have no '.', '!', '?' - confirm
    the returned overlap is small, not the entire input text."""
    table_text = "Name | Age | City\nAlice | 30 | Delhi\nBob | 25 | Mumbai\nCarol | 40 | Pune"
    tail = _take_overlap_tail(table_text, overlap_tokens=8)
    assert len(tail) < len(table_text)
    assert tail != table_text


def test_chunking_a_large_spreadsheet_never_produces_a_chunk_over_the_openai_embedding_limit():
    """Regression test for both bugs combined: chunking a realistically
    large, table-heavy document must never produce a chunk anywhere near
    OpenAI's 8,191-token hard limit for embedding inputs, and chunk sizes
    must stabilize rather than grow without bound (the snowball bug's
    actual signature was monotonic growth across every single chunk, not
    merely "larger than the target size", which legitimate table-packed
    chunks can be)."""
    document = _make_large_table_document(num_rows=1200, num_cols=16)
    chunks = chunk_document(document, chunk_size_tokens=512, overlap_tokens=64)
    sizes = [c.token_count for c in chunks]

    max_tokens = max(sizes)
    assert max_tokens < 8191, f"chunk of {max_tokens} tokens would be rejected by the real OpenAI embedding API"

    # The snowball bug's signature: every non-overlap chunk strictly larger
    # than the last, unbounded, across the whole document. A healthy
    # chunker plateaus. Compare the last quarter of chunks' sizes against
    # the first quarter - the snowball bug made the tail 5-10x the head;
    # a fixed chunker keeps them within a small, bounded factor.
    quarter = max(len(sizes) // 4, 1)
    head_avg = sum(sizes[:quarter]) / quarter
    tail_avg = sum(sizes[-quarter:]) / quarter
    assert tail_avg < head_avg * 3, (
        f"tail chunks averaging {tail_avg:.0f} tokens vs head chunks averaging {head_avg:.0f} tokens "
        f"suggests the overlap snowball bug has returned"
    )
