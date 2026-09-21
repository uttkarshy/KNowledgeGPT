import fitz

from app.core.config import Settings
from app.services.extraction.pdf_extractor import PDFExtractor


def test_pdf_range_preserves_global_page_numbers(tmp_path):
    path = tmp_path / "large.pdf"
    doc = fitz.open()
    for page_number in range(1, 301):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {page_number} has enough native text for bounded extraction.")
    doc.save(path)
    doc.close()

    extractor = PDFExtractor()
    settings = Settings(MAX_PDF_PAGES=500, PDF_PAGE_BATCH_SIZE=25)
    assert extractor.page_count(str(path), settings=settings) == 300
    batch = extractor.extract_range(str(path), settings=settings, start_page=276, end_page=300)
    assert batch.page_count == 300
    assert [page.page_number for page in batch.pages] == list(range(276, 301))
    assert all(block.page_number == page.page_number for page in batch.pages for block in page.blocks)
