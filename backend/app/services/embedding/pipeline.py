"""
Embedding pipeline — the final stage of the upload pipeline.

    extracted text -> semantic chunks -> batched embedding calls -> DocumentChunk rows
    -> update Document/KnowledgeBase counters -> delete original from S3

This is the ONLY place that connects the extraction/chunking layer to the
LLM provider layer and the database. It depends on LLMProvider (never a
concrete provider), so switching embedding backends per the provider
abstraction doesn't touch this file.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aws import delete_object
from app.core.config import Settings
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.llm import EmbeddingRequest
from app.services.chunking.semantic_chunker import Chunk, chunk_document
from app.services.extraction.registry import get_extractor
from app.services.extraction.schemas import ExtractionError, UnsupportedFormatError
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_EMBEDDING_BATCH_SIZE = 100  # keeps individual API calls within reasonable payload size


class EmbeddingPipelineError(Exception):
    pass


def _chunk_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def process_document_embeddings(
    db: AsyncSession,
    *,
    settings: Settings,
    provider: LLMProvider,
    document_id: uuid.UUID,
    local_file_path: str,
) -> int:
    """Runs extraction -> chunking -> embedding -> storage for one document.

    `local_file_path` must already point to the downloaded file on local
    disk (the Celery task downloads from S3 before calling this — this
    function never talks to S3 for the *input* file, only for deleting the
    original on success). Returns the number of chunks written. Raises on
    any unrecoverable failure; callers are responsible for marking the
    document FAILED and deciding whether the S3 original should be kept
    for retry or deleted.
    """
    document = await db.get(Document, document_id)
    if document is None:
        raise EmbeddingPipelineError(f"Document {document_id} not found")

    # ---------------- Extraction ----------------
    try:
        extractor = get_extractor(document.file_type)
    except UnsupportedFormatError as e:
        raise EmbeddingPipelineError(str(e)) from e

    try:
        extracted = extractor.extract(local_file_path, settings=settings)
    except ExtractionError as e:
        raise EmbeddingPipelineError(f"Extraction failed: {e}") from e

    document.page_count = extracted.page_count
    document.language = extracted.detected_language
    document.status = DocumentStatus.CHUNKING
    document.processing_progress_pct = 50
    await db.flush()

    # ---------------- Chunking ----------------
    chunks: list[Chunk] = chunk_document(extracted)
    if not chunks:
        raise EmbeddingPipelineError("No extractable text content found in this document")

    document.status = DocumentStatus.EMBEDDING
    document.processing_progress_pct = 60
    await db.flush()

    # ---------------- Embedding (batched) ----------------
    embedding_model = settings.LLM_EMBEDDING_MODEL
    stored_count = 0

    for batch_start in range(0, len(chunks), _EMBEDDING_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + _EMBEDDING_BATCH_SIZE]
        try:
            result = await provider.embed(EmbeddingRequest(texts=[c.text for c in batch]))
        except Exception as e:  # provider already normalizes its own exceptions
            raise EmbeddingPipelineError(f"Embedding generation failed: {e}") from e

        if len(result.embeddings) != len(batch):
            raise EmbeddingPipelineError(
                f"Embedding count mismatch: sent {len(batch)} texts, got {len(result.embeddings)} vectors back"
            )

        for i, chunk in enumerate(batch):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    knowledge_base_id=document.knowledge_base_id,
                    owner_id=document.owner_id,
                    chunk_index=batch_start + i,
                    page_number=chunk.page_number,
                    section=chunk.section_title,
                    content=chunk.text,
                    token_count=chunk.token_count,
                    embedding=result.embeddings[i],
                    embedding_model=embedding_model,
                    checksum=_chunk_checksum(chunk.text),
                )
            )
            stored_count += 1

        progress = 60 + int(30 * (batch_start + len(batch)) / len(chunks))
        document.processing_progress_pct = min(progress, 90)
        await db.flush()

    # ---------------- Finalize ----------------
    document.chunk_count = stored_count
    document.embedding_model = embedding_model
    document.status = DocumentStatus.COMPLETED
    document.status_detail = None
    document.processing_progress_pct = 100

    kb = await db.get(KnowledgeBase, document.knowledge_base_id)
    if kb:
        kb.document_count += 1
        kb.total_chunk_count += stored_count

    await db.flush()

    # ---------------- Delete original from S3 (storage rule) ----------------
    # Only ever deleted here, after embeddings are durably written to the
    # DB session (flushed, about to be committed by the caller's `async with`
    # block) — never before, and never on a failure path.
    if document.temp_storage_key:
        s3_key = document.temp_storage_key
        document.temp_storage_key = None
        delete_object(settings=settings, key=s3_key)

    return stored_count
