from app.services.chunking.semantic_chunker import chunk_document
from app.services.extraction.schemas import ExtractedBlock, ExtractedDocument, ExtractedPage, SectionKind


def _doc(blocks):
    return ExtractedDocument(pages=[ExtractedPage(page_number=1, blocks=blocks)], page_count=1)


def test_heading_forces_new_chunk_boundary():
    blocks = [
        ExtractedBlock(kind=SectionKind.HEADING, text="Introduction", heading_level=1, section_title="Introduction"),
        ExtractedBlock(kind=SectionKind.PARAGRAPH, text="This is the intro paragraph with some content.", section_title="Introduction"),
        ExtractedBlock(kind=SectionKind.HEADING, text="Methodology", heading_level=1, section_title="Methodology"),
        ExtractedBlock(kind=SectionKind.PARAGRAPH, text="This describes our methodology in detail.", section_title="Methodology"),
    ]
    chunks = chunk_document(_doc(blocks), chunk_size_tokens=512, overlap_tokens=0)
    assert len(chunks) == 2
    assert chunks[0].section_title == "Introduction"
    assert chunks[1].section_title == "Methodology"


def test_table_stays_atomic_and_isolated():
    blocks = [
        ExtractedBlock(kind=SectionKind.PARAGRAPH, text="Some intro text before the table."),
        ExtractedBlock(kind=SectionKind.TABLE, text="Name | Age\nAlice | 30\nBob | 25"),
        ExtractedBlock(kind=SectionKind.PARAGRAPH, text="Some text after the table."),
    ]
    chunks = chunk_document(_doc(blocks), chunk_size_tokens=512, overlap_tokens=0)
    table_chunks = [c for c in chunks if "Alice" in c.text]
    assert len(table_chunks) == 1
    assert "Bob" in table_chunks[0].text
    assert "intro text" not in table_chunks[0].text
    assert "after the table" not in table_chunks[0].text


def test_oversized_paragraph_splits_at_sentence_boundaries():
    long_text = " ".join(f"This is sentence number {i} with some extra padding words to grow it." for i in range(60))
    chunks = chunk_document(_doc([ExtractedBlock(kind=SectionKind.PARAGRAPH, text=long_text)]), chunk_size_tokens=50, overlap_tokens=0)
    assert len(chunks) > 1
    for c in chunks:
        assert c.text.strip().endswith("."), f"chunk does not end on a sentence boundary: {c.text[-30:]!r}"


def test_overlap_carries_into_next_chunk():
    blocks = [
        ExtractedBlock(kind=SectionKind.PARAGRAPH, text="Alpha sentence one. Alpha sentence two. Alpha sentence three."),
        ExtractedBlock(kind=SectionKind.PARAGRAPH, text="Beta sentence one. Beta sentence two. Beta sentence three."),
    ]
    chunks = chunk_document(_doc(blocks), chunk_size_tokens=12, overlap_tokens=8)
    assert len(chunks) >= 2
    assert any(word in chunks[1].text for word in chunks[0].text.split()[-3:])
