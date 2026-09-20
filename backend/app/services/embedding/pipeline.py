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
import math
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.llm import EmbeddingRequest
from app.services.chunking.semantic_chunker import Chunk, bound_chunk_bytes, chunk_document
from app.services.extraction.registry import get_extractor
from app.services.llm.base import LLMProvider
from app.services.processing_errors import ProcessingFailure

logger = logging.getLogger(__name__)



class EmbeddingPipelineError(ProcessingFailure):
    def __init__(self, message: str):
        super().__init__("embedding_failure", "Embedding processing failed. Retry Processing later or contact support.", retryable=True)


def _chunk_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def process_document_embeddings(
    db: AsyncSession,
    *,
    settings: Settings,
    provider: LLMProvider,
    document_id: uuid.UUID,
    local_file_path: str,
    on_progress: Callable[..., Awaitable[None]] | None = None,
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

    if document.status == DocumentStatus.COMPLETED:
        return document.chunk_count
    await db.commit()  # no transaction held while extracting or updating progress
    extractor = get_extractor(document.file_type)
    extracted = extractor.extract(local_file_path, settings=settings)

    document.page_count = extracted.page_count
    document.language = extracted.detected_language
    document.status = DocumentStatus.CHUNKING
    document.processing_progress_pct = 50
    if on_progress:
        await on_progress(str(document_id), status=DocumentStatus.CHUNKING, detail=None, progress=50)

    # ---------------- Chunking ----------------
    chunks: list[Chunk] = bound_chunk_bytes(chunk_document(extracted), settings.EMBEDDING_MAX_INPUT_BYTES)
    if not chunks:
        raise ProcessingFailure("no_extractable_content", "No extractable content was found. Upload a clearer or text-based file.")
    if len(chunks) > settings.MAX_CHUNKS_PER_DOCUMENT:
        raise ProcessingFailure("document_limit_exceeded", "Document exceeds the safe processing limit. Split it into smaller documents.")

    document.status = DocumentStatus.EMBEDDING
    document.processing_progress_pct = 60
    if on_progress:
        await on_progress(str(document_id), status=DocumentStatus.EMBEDDING, detail=None, progress=60)
    # The worker's document advisory lock serializes duplicate deliveries.
    # Only COMPLETED documents are visible to retrieval.
    embedding_model = settings.LLM_EMBEDDING_MODEL
    existing = list((await db.scalars(select(DocumentChunk).where(
        DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index))).all())
    valid = all(0 <= row.chunk_index < len(chunks)
                and row.checksum == _chunk_checksum(chunks[row.chunk_index].text)
                and row.embedding_model == embedding_model
                and row.structure == chunks[row.chunk_index].structure for row in existing)
    if not valid:
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        existing = []
    done = {row.chunk_index for row in existing}
    await db.commit()
    pending = [(i,chunk) for i,chunk in enumerate(chunks) if i not in done]
    stored_count = len(done)
    for offset in range(0,len(pending),settings.EMBEDDING_BATCH_SIZE):
        indexed_batch = pending[offset:offset+settings.EMBEDDING_BATCH_SIZE]
        batch = [chunk for _,chunk in indexed_batch]
        result = await provider.embed(EmbeddingRequest(texts=[c.text for c in batch]))

        if len(result.embeddings) != len(batch):
            raise EmbeddingPipelineError(
                f"Embedding count mismatch: sent {len(batch)} texts, got {len(result.embeddings)} vectors back"
            )
        if result.model != embedding_model or result.dimensions != settings.LLM_EMBEDDING_DIMENSIONS:
            raise EmbeddingPipelineError("Embedding model/dimension does not match configuration")
        if any(len(v) != settings.LLM_EMBEDDING_DIMENSIONS or not all(math.isfinite(x) for x in v) or not any(v) for v in result.embeddings):
            raise EmbeddingPipelineError("Provider returned an invalid embedding vector")

        for i, chunk in enumerate(batch):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    knowledge_base_id=document.knowledge_base_id,
                    owner_id=document.owner_id,
                    chunk_index=indexed_batch[i][0],
                    structure=chunk.structure,
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

        progress = 60 + int(30 * stored_count / len(chunks))
        document.processing_progress_pct = min(progress, 90)
        await db.commit()  # save each completed batch before the next paid call

    # ---------------- Finalize ----------------
    document.chunk_count = stored_count
    document.embedding_model = embedding_model
    document.status = DocumentStatus.COMPLETED
    document.status_detail = None
    document.error_code = None
    document.retryable = False
    document.next_retry_at = None
    document.processing_progress_pct = 100

    await db.execute(update(KnowledgeBase).where(KnowledgeBase.id == document.knowledge_base_id).values(
        document_count=KnowledgeBase.document_count + 1,
        total_chunk_count=KnowledgeBase.total_chunk_count + stored_count,
    ))

    await db.flush()

    # ---------------- Delete original from S3 (storage rule) ----------------
    # Only ever deleted here, after embeddings are durably written to the
    # DB session (flushed, about to be committed by the caller's `async with`
    # block) — never before, and never on a failure path.
    # The worker deletes the original only AFTER this transaction commits.

    return stored_count
