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

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.usage import ApiUsageLog
from app.schemas.llm import EmbeddingRequest
from app.services import credit_service
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
    await db.commit()
    extractor = get_extractor(document.file_type)
    embedding_model = settings.LLM_EMBEDDING_MODEL
    is_pdf = document.file_type.value == "pdf"
    total_pages = extractor.page_count(local_file_path, settings=settings) if is_pdf else 1
    document.page_count = total_pages if is_pdf else document.page_count
    document.estimated_credits = max(1, total_pages) * settings.DOCUMENT_CREDITS_PER_PAGE
    await db.commit()

    all_page_ranges = (
        [(start, min(start + settings.PDF_PAGE_BATCH_SIZE - 1, total_pages))
         for start in range(1, total_pages + 1, settings.PDF_PAGE_BATCH_SIZE)]
        if is_pdf else [(1, 1)]
    )
    completed_pages = document.processed_page_count or 0
    page_ranges = [bounds for bounds in all_page_ranges if bounds[1] > completed_pages]
    completed_chunk_count = await db.scalar(select(func.count(DocumentChunk.id)).where(
        DocumentChunk.document_id == document.id,
        DocumentChunk.page_number <= completed_pages,
    )) if completed_pages else 0
    stored_count = int(completed_chunk_count or 0)
    global_chunk_index = stored_count
    found_content = stored_count > 0
    for start_page, end_page in page_ranges:
        page_credits = max(1, end_page - start_page + 1) * settings.DOCUMENT_CREDITS_PER_PAGE
        charge_key = f"document:{document.id}:pages:{start_page}-{end_page}"
        try:
            charged = await credit_service.charge(
                db, user_id=document.owner_id, credits=page_credits,
                operation="document.process", idempotency_key=charge_key,
                model=embedding_model,
                metadata={"document_id": str(document.id), "start_page": start_page, "end_page": end_page},
            )
            await db.commit()
        except credit_service.InsufficientCreditsError as exc:
            raise ProcessingFailure("insufficient_credits", str(exc), retryable=True) from exc

        provider_called = False
        try:
            extracted = (
                extractor.extract_range(local_file_path, settings=settings, start_page=start_page, end_page=end_page)
                if is_pdf else extractor.extract(local_file_path, settings=settings)
            )
            document.language = document.language or extracted.detected_language
            document.status = DocumentStatus.CHUNKING
            chunks: list[Chunk] = bound_chunk_bytes(chunk_document(extracted), settings.EMBEDDING_MAX_INPUT_BYTES)
            found_content = found_content or bool(chunks)
            if global_chunk_index + len(chunks) > settings.MAX_CHUNKS_PER_DOCUMENT:
                raise ProcessingFailure("document_limit_exceeded", "Document exceeds the safe processing limit. Split it into smaller documents.")

            existing = list((await db.scalars(select(DocumentChunk).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.chunk_index >= global_chunk_index,
                DocumentChunk.chunk_index < global_chunk_index + len(chunks),
            ).order_by(DocumentChunk.chunk_index))).all())
            expected = {global_chunk_index + i: chunk for i, chunk in enumerate(chunks)}
            if any(row.chunk_index not in expected
                   or row.checksum != _chunk_checksum(expected[row.chunk_index].text)
                   or row.embedding_model != embedding_model
                   or row.structure != expected[row.chunk_index].structure for row in existing):
                await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
                await db.commit()
                raise EmbeddingPipelineError("Saved checkpoint no longer matches extracted content")
            done = {row.chunk_index for row in existing}
            pending = [(global_chunk_index + i, chunk) for i, chunk in enumerate(chunks)
                       if global_chunk_index + i not in done]
            stored_count += len(existing)

            document.status = DocumentStatus.EMBEDDING
            for offset in range(0, len(pending), settings.EMBEDDING_BATCH_SIZE):
                indexed_batch = pending[offset:offset + settings.EMBEDDING_BATCH_SIZE]
                batch = [chunk for _, chunk in indexed_batch]
                provider_called = True
                result = await provider.embed(EmbeddingRequest(texts=[c.text for c in batch]))
                if len(result.embeddings) != len(batch):
                    raise EmbeddingPipelineError("Embedding count mismatch")
                if result.model != embedding_model or result.dimensions != settings.LLM_EMBEDDING_DIMENSIONS:
                    raise EmbeddingPipelineError("Embedding model/dimension does not match configuration")
                if any(len(v) != settings.LLM_EMBEDDING_DIMENSIONS or not all(math.isfinite(x) for x in v) or not any(v) for v in result.embeddings):
                    raise EmbeddingPipelineError("Provider returned an invalid embedding vector")
                for i, chunk in enumerate(batch):
                    db.add(DocumentChunk(
                        document_id=document.id, knowledge_base_id=document.knowledge_base_id,
                        owner_id=document.owner_id, chunk_index=indexed_batch[i][0],
                        structure=chunk.structure, page_number=chunk.page_number,
                        section=chunk.section_title, content=chunk.text,
                        token_count=chunk.token_count, embedding=result.embeddings[i],
                        embedding_model=embedding_model, checksum=_chunk_checksum(chunk.text),
                    ))
                    stored_count += 1
                await db.execute(update(ApiUsageLog).where(
                    ApiUsageLog.idempotency_key == charge_key
                ).values(
                    input_tokens=ApiUsageLog.input_tokens + sum(chunk.token_count for chunk in batch),
                    usage_metadata={
                        "document_id": str(document.id), "start_page": start_page,
                        "end_page": end_page, "embedding_tokens_are_estimated": True,
                    },
                ))
                await db.commit()
            document.processed_page_count = end_page if is_pdf else 1
            document.processing_progress_pct = 20 + int(70 * document.processed_page_count / total_pages)
            await db.commit()
            global_chunk_index += len(chunks)
        except Exception:
            if charged and not provider_called:
                await db.rollback()
                await credit_service.refund(
                    db, user_id=document.owner_id, credits=page_credits,
                    operation="document.refund", idempotency_key=f"refund:{charge_key}",
                    metadata={"reason": "failed_before_provider_call"},
                )
                await db.commit()
            raise

    if not found_content:
        raise ProcessingFailure("no_extractable_content", "No extractable content was found. Upload a clearer or text-based file.")

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
