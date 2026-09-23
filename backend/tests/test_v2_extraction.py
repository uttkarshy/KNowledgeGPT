import subprocess
import time
import uuid

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings
from app.services.chunking.semantic_chunker import bound_chunk_bytes, chunk_document
from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.extraction.schemas import ExtractedDocument, ExtractedPage
from app.services.extraction.table_rows import row_block
from app.services.ocr.structured import scanned_page
from app.services.processing_errors import ProcessingFailure
from app.services.rag.exhaustive import named_rows
from app.services.rag.retrieval import RetrievedChunk


def test_row_integrity_page_and_unknown_cells():
    block = row_block(
        ["NAME", "ACCOUNT No.", "IFSC CODE", "NET PAYABLE"],
        ["Example Person", "1234567890", "TEST0123456", ""],
        page_number=2,
        table_id=0,
        row_index=7,
    )
    chunks = bound_chunk_bytes(chunk_document(ExtractedDocument(pages=[ExtractedPage(2, [block])], page_count=1)), 1800)
    assert len(chunks) == 1 and chunks[0].structure["row_index"] == 7
    row = RetrievedChunk(
        uuid.uuid4(), uuid.uuid4(), "synthetic.pdf", chunks[0].text, 2, None, 1, structure=chunks[0].structure
    )
    answer, sources = named_rows([row], ("Example Person",))
    assert "Could not be reliably extracted" in answer and "Page 2" in answer and sources == [row]
    with pytest.raises(ValueError):
        named_rows([row], ("Another Person",))
    with pytest.raises(ProcessingFailure):
        bound_chunk_bytes(chunks, 10)


def test_pdf_limit_specific_and_before_ocr(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.pdf"
    with fitz.open() as doc:
        for _ in range(3):
            doc.new_page()
        doc.save(path)
    monkeypatch.setattr(
        "app.services.extraction.pdf_extractor.scanned_page", lambda *a: pytest.fail("OCR must not run")
    )
    with pytest.raises(ProcessingFailure) as error:
        PDFExtractor().extract(str(path), settings=Settings(MAX_PDF_PAGES=2))
    assert error.value.code == "page_limit_exceeded"
    assert "3 pages" in str(error.value) and "2 pages" in str(error.value)


def test_native_pdf_stays_on_fast_path(tmp_path, monkeypatch):
    path = tmp_path / "resume.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 100), "Synthetic Candidate holds a Master of Computer Applications degree.")
        doc.save(path)
    monkeypatch.setattr(
        "app.services.extraction.pdf_extractor.scanned_page", lambda *a: pytest.fail("native text must not use OCR")
    )
    extracted = PDFExtractor().extract(str(path), settings=Settings())
    assert "Master of Computer Applications" in " ".join(b.text for b in extracted.all_blocks())
    assert not extracted.pages[0].was_ocr


def test_pathological_native_table_discovery_is_bounded(monkeypatch):
    from app.services.extraction import pdf_extractor

    class BlockingPage:
        def find_tables(self):
            time.sleep(1)
            return type("Tables", (), {"tables": []})()

    monkeypatch.setattr(pdf_extractor, "_TABLE_EXTRACTION_TIMEOUT_SECONDS", 0.02)
    started = time.monotonic()
    with pytest.raises(ProcessingFailure) as error:
        PDFExtractor()._extract_native_blocks(BlockingPage(), 1, None)
    assert time.monotonic() - started < 0.5
    assert error.value.code == "processing_timeout"
    assert error.value.retryable is True


def test_ocr_language_discovery_subprocess_is_bounded(monkeypatch):
    from app.services.ocr import structured

    structured._installed_languages.cache_clear()
    monkeypatch.setattr(
        structured.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        ),
    )
    with pytest.raises(RuntimeError, match="language discovery"):
        structured._installed_languages()
    structured._installed_languages.cache_clear()


def test_real_rotated_image_ocr_has_page_identity():
    image = Image.new("RGB", (1100, 650), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    for i in range(10):
        draw.text(
            (40, 30 + i * 55),
            f"Synthetic example document row {i}. School library opens Monday.",
            font=font,
            fill="black",
        )
    page = scanned_page(image.rotate(90, expand=True), 3)
    assert page.was_ocr and page.page_number == 3
    assert "library" in " ".join(b.text for b in page.blocks).lower()
    assert all(b.page_number == 3 for b in page.blocks)
    assert any(b.structure.get("rotation") in (90, 270) for b in page.blocks)


def test_uncertain_lines_packed_without_losing_boundaries():
    from app.services.extraction.schemas import ExtractedBlock, SectionKind
    from app.services.ocr.structured import pack_ocr_lines

    texts = [f"Synthetic spatial line {i}" for i in range(100)]
    blocks = [
        ExtractedBlock(
            SectionKind.PARAGRAPH,
            text,
            page_number=4,
            structure={"kind": "ocr_line", "row_index": i, "uncertain_structure": True},
        )
        for i, text in enumerate(texts)
    ]
    packed = pack_ocr_lines(blocks)
    assert len(packed) < 5
    assert "\n".join(b.text for b in packed).splitlines() == texts
    assert all(len(b.text.encode()) <= 900 and b.page_number == 4 for b in packed)
    assert packed[-1].structure["last_line_index"] == 99
    assert all(b.structure["uncertain_structure"] for b in packed)


def test_uncertain_ocr_is_not_a_named_row_and_is_labelled():
    from app.services.rag.prompt_assembly import build_source_list

    row = RetrievedChunk(
        uuid.uuid4(),
        uuid.uuid4(),
        "synthetic.pdf",
        "Example Person 1000",
        1,
        None,
        1,
        structure={"kind": "ocr_line", "uncertain_structure": True},
    )
    with pytest.raises(ValueError):
        named_rows([row], ("Example Person",))
    assert "relationships uncertain" in build_source_list([row])


@pytest.mark.parametrize("extension", ["png", "jpg"])
def test_standalone_image_ingestion_extracts_text(tmp_path, extension):
    from app.services.extraction.image_extractor import ImageExtractor

    image = Image.new("RGB", (1000, 300), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    draw = ImageDraw.Draw(image)
    for i in range(4):
        draw.text((35, 30 + i * 55), "Synthetic school library opens Monday.", font=font, fill="black")
    path = tmp_path / f"synthetic.{extension}"
    image.save(path)
    extracted = ImageExtractor().extract(str(path), settings=Settings())
    assert "library" in " ".join(b.text for b in extracted.all_blocks()).lower()
    assert all(b.page_number == 1 for b in extracted.all_blocks())


def test_headerless_csv_and_extra_cells_not_discarded(tmp_path):
    from app.services.extraction.csv_extractor import CSVExtractor

    path = tmp_path / "synthetic.csv"
    path.write_text("Alice,100\nBob,200\n")
    extracted = CSVExtractor().extract(str(path), settings=Settings())
    assert "Alice" in " ".join(b.text for b in extracted.all_blocks())
    row = row_block(["NAME"], ["Example", "extra cell"], page_number=1, table_id=0, row_index=1)
    assert "extra cell" in row.text
