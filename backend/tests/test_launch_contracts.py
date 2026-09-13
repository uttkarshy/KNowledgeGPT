import uuid
from unittest.mock import AsyncMock

import fitz
import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.models.chat import ChatMessage
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.usage import AuditLog
from app.models.user import User
from app.schemas.chat import AskQuestionRequest
from app.services.chunking.semantic_chunker import bound_chunk_bytes, chunk_document
from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.rag.retrieval import similarity_search
from app.services.upload.validation import FileValidationError, validate_uploaded_file


def test_all_orm_enum_values_match_lowercase_migration_values():
    for model, fields in [(User, ["role", "auth_provider"]), (Document, ["status", "file_type"]),
                          (ChatMessage, ["role"]), (AuditLog, ["action"])]:
        for field in fields:
            values = model.__table__.c[field].type.enums
            assert all(v == v.lower() for v in values)
    assert DocumentChunk.__table__.c.embedding.type.dim == 1536
    with pytest.raises(ValidationError):
        Settings(LLM_EMBEDDING_DIMENSIONS=3072)


def test_question_and_production_configuration_limits():
    for question in [" ", "a"*601, "😀"*500]:
        with pytest.raises(ValidationError):
            AskQuestionRequest(question=question)
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production")


def test_real_pdf_extraction_and_bounded_chunks(tmp_path):
    path = tmp_path / "acceptance.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "The KnowledgeGPT test library opens at 9 AM and closes at 5 PM.")
    document.save(path)
    document.close()
    settings = Settings()
    validated = validate_uploaded_file(file_path=str(path), filename=path.name, size_bytes=path.stat().st_size, settings=settings)
    assert validated.file_type.value == "pdf"
    extracted = PDFExtractor().extract(str(path), settings=settings)
    chunks = bound_chunk_bytes(chunk_document(extracted), settings.EMBEDDING_MAX_INPUT_BYTES)
    assert chunks and chunks[0].page_number == 1
    assert "9 AM" in chunks[0].text
    assert all(len(c.text.encode()) <= 1800 for c in chunks)


def test_fake_pdf_fails_magic_validation(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_text("This is not a PDF")
    with pytest.raises(FileValidationError):
        validate_uploaded_file(file_path=str(path), filename=path.name, size_bytes=path.stat().st_size, settings=Settings())


@pytest.mark.asyncio
async def test_retrieval_query_scopes_owner_kb_model_and_completed_documents():
    owner, kb = uuid.uuid4(), uuid.uuid4()
    class Result:
        def all(self): return []
    db = AsyncMock()
    db.execute.return_value = Result()
    assert await similarity_search(db, owner_id=owner, knowledge_base_id=kb,
                                   query_embedding=[0.1]*1536, embedding_model="gemini-embedding-001") == []
    stmt = db.execute.call_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    values = stmt.compile().params
    assert "document_chunks.owner_id =" in sql and "documents.owner_id =" in sql
    assert "document_chunks.knowledge_base_id =" in sql and "documents.knowledge_base_id =" in sql
    assert "document_chunks.embedding_model =" in sql and "documents.status =" in sql
    assert owner in values.values() and kb in values.values()


@pytest.mark.parametrize("reply,infected", [(b"stream: OK\0", False), (b"stream: Eicar-Test-Signature FOUND\0", True)])
def test_clamav_null_terminated_response(tmp_path, monkeypatch, reply, infected):
    from unittest.mock import MagicMock
    from app.services.upload.virus_scan import scan_file, VirusFoundError
    path = tmp_path / "payload.txt"
    path.write_text("test bytes")
    socket = MagicMock()
    socket.recv.side_effect = [reply[:5], reply[5:]]
    socket.__enter__.return_value = socket
    monkeypatch.setattr("app.services.upload.virus_scan.socket.create_connection", lambda *a, **kw: socket)
    if infected:
        with pytest.raises(VirusFoundError): scan_file(file_path=str(path), settings=Settings())
    else:
        scan_file(file_path=str(path), settings=Settings())


def test_xml_external_entities_are_rejected(tmp_path):
    from app.services.extraction.xml_extractor import XMLExtractor
    from app.services.extraction.schemas import ExtractionError
    path = tmp_path / "external.xml"
    path.write_text('<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>')
    with pytest.raises(ExtractionError): XMLExtractor().extract(str(path), settings=Settings())
