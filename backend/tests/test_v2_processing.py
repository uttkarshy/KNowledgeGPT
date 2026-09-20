import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai.errors import ClientError

from app.core.config import Settings
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.schemas.llm import EmbeddingResult
from app.services import document_service
from app.services.chunking.semantic_chunker import Chunk
from app.services.embedding import pipeline
from app.services.llm.base import LLMRateLimitError
from app.services.llm.gemini_provider import _translate_error
from app.services.processing_errors import classify, retry_delay


def test_quota_metadata_backoff_and_safe_messages():
    error = ClientError(
        429,
        {"error": {"status": "RESOURCE_EXHAUSTED", "message": "private payload", "details": [{"retryDelay": "125s"}]}},
        response=SimpleNamespace(headers={"Retry-After": "130"}),
    )
    translated = _translate_error(error)
    assert isinstance(translated, LLMRateLimitError) and translated.retry_after == 130
    assert "private" not in str(translated)
    assert classify(translated, "embedding").code == "provider_rate_limited"
    assert retry_delay(0, 30, 130) == 130
    assert 120 <= retry_delay(2, 30) <= 150
    assert retry_delay(20, 30) <= 930


async def test_successful_batches_survive_quota_and_retry_skips_them(monkeypatch):
    doc = Document(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        file_type=FileType.TXT,
        status=DocumentStatus.EXTRACTING,
    )
    chunks = [Chunk(f"Synthetic unique row {i}", 1, None, 5) for i in range(4)]
    monkeypatch.setattr(
        pipeline,
        "get_extractor",
        lambda _: SimpleNamespace(extract=lambda *a, **kw: SimpleNamespace(page_count=1, detected_language="en")),
    )
    monkeypatch.setattr(pipeline, "chunk_document", lambda _: chunks)
    saved, pending = [], []
    db = AsyncMock()
    db.get.return_value = doc
    db.scalars.side_effect = lambda _: SimpleNamespace(all=lambda: list(saved))
    db.add = pending.append

    async def commit():
        saved.extend(pending)
        pending.clear()

    db.commit.side_effect = commit
    result = EmbeddingResult(embeddings=[[1.0] + [0.0] * 1535] * 2, dimensions=1536, model="gemini-embedding-001")
    provider = SimpleNamespace(embed=AsyncMock(side_effect=[result, LLMRateLimitError("quota")]))
    settings = Settings(EMBEDDING_BATCH_SIZE=2)
    with pytest.raises(LLMRateLimitError):
        await pipeline.process_document_embeddings(
            db, settings=settings, provider=provider, document_id=doc.id, local_file_path="synthetic"
        )
    assert [c.chunk_index for c in saved] == [0, 1]
    assert doc.status != DocumentStatus.COMPLETED
    provider.embed = AsyncMock(return_value=result)
    assert (
        await pipeline.process_document_embeddings(
            db, settings=settings, provider=provider, document_id=doc.id, local_file_path="synthetic"
        )
        == 4
    )
    assert [c.chunk_index for c in saved] == [0, 1, 2, 3]
    assert provider.embed.await_count == 1
    assert provider.embed.call_args.args[0].texts == [chunks[2].text, chunks[3].text]
    await pipeline.process_document_embeddings(
        db, settings=settings, provider=provider, document_id=doc.id, local_file_path="synthetic"
    )
    assert provider.embed.await_count == 1


async def test_duplicate_retry_is_idempotent_and_owner_lookup_rejects_missing(monkeypatch):
    db = AsyncMock()
    doc = SimpleNamespace(status=DocumentStatus.EMBEDDING)
    db.scalar.return_value = doc
    monkeypatch.setattr(
        "app.workers.tasks.document_processing.process_document",
        SimpleNamespace(delay=lambda *a: pytest.fail("duplicate enqueued")),
    )
    assert (
        await document_service.retry_processing(
            db, settings=Settings(), document_id=uuid.uuid4(), owner_id=uuid.uuid4()
        )
        is doc
    )
    db.commit.assert_not_awaited()
    db.scalar.return_value = None
    with pytest.raises(document_service.DocumentNotFoundError):
        await document_service.retry_processing(
            db, settings=Settings(), document_id=uuid.uuid4(), owner_id=uuid.uuid4()
        )
