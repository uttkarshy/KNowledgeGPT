"""
Document processing pipeline (Celery task).

Full pipeline: download from S3 -> virus scan -> file validation ->
semantic chunking -> embedding generation -> delete S3 original on success.

Event-loop architecture
------------------------
Exactly ONE `asyncio.run()` call happens per task invocation, in the
synchronous Celery entrypoint `process_document()` at the bottom of this
file. Everything the pipeline needs to await - loading the document,
every status update, the embedding pipeline's own DB work - happens
inside `process_document_async()`, a single coroutine, using `await`
throughout. There are no nested `asyncio.run()` calls anywhere in this
file.

This replaces an earlier version of this file that called a `_run_async()`
helper (`asyncio.run(coro)`) separately for each sub-step - once to load
the document, once per status update, once more for the embedding
pipeline. Each of those calls created and tore down its OWN event loop.
asyncpg's connections (and the asyncio.Future objects it uses internally)
are bound to whichever loop was running when they were opened; the
shared, module-level SQLAlchemy engine (app/db/session.py) could hand
back a connection whose internal Future belonged to an already-closed
loop the moment a later step's `asyncio.run()` created a new one - which
is exactly what raised `RuntimeError: Future attached to a different
loop`. See app/db/session.py's `dispose_engine()` docstring for the other
half of this fix: the engine's pool is also disposed at the end of this
task's single loop, so no connection can leak into the NEXT task's
separate `asyncio.run()` call either.

Reliability guarantee (unchanged from before this refactor): every
failure path - anticipated (S3 error, virus found, validation failure,
embedding failure) or unanticipated - ends with the document transitioned
to FAILED with a human-readable reason, never left silently stuck at
whatever status was last set.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone

from celery import Task
from celery.exceptions import Retry
from sqlalchemy import text

from app.core.aws import S3Error, delete_object, download_to_path
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, dispose_engine
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.embedding.pipeline import EmbeddingPipelineError, process_document_embeddings
from app.services.llm.base import LLMProviderError
from app.services.llm.factory import build_llm_provider
from app.services.processing_errors import ProcessingFailure, classify, retry_delay
from app.services.upload.validation import validate_uploaded_file
from app.services.upload.virus_scan import VirusFoundError, VirusScanUnavailableError, scan_file
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Terminal processing failure, also visible in Celery's result state."""


async def _update_status(document_id: str, *, status: DocumentStatus, detail: str | None, progress: int) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, uuid.UUID(document_id))
        if document is None:
            return
        document.status = status
        document.status_detail = detail
        document.processing_progress_pct = progress
        await db.commit()
    logger.info("document=%s stage=%s progress=%d", document_id, status.value, progress)


async def _load_document(document_id: str) -> Document | None:
    async with AsyncSessionLocal() as db:
        return await db.get(Document, uuid.UUID(document_id))


async def _fail(document_id: str, detail: str) -> None:
    await _update_status(document_id, status=DocumentStatus.FAILED, detail=detail, progress=0)


async def _record_failure(document_id: str, failure: ProcessingFailure, delay: float | None = None) -> None:
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, uuid.UUID(document_id))
        if not doc:
            return
        doc.error_code = failure.code
        doc.last_error_code = failure.code
        doc.last_error_at = datetime.now(timezone.utc)
        doc.retryable = failure.retryable and bool(doc.temp_storage_key)
        doc.next_retry_at = datetime.now(timezone.utc)+timedelta(seconds=delay) if delay is not None else None
        if failure.code == 'provider_rate_limited':
            doc.provider_rate_limit_count = (doc.provider_rate_limit_count or 0)+1
        if delay is not None:
            doc.automatic_retries = (doc.automatic_retries or 0)+1
            doc.status = DocumentStatus.EMBEDDING
            doc.status_detail = ('AI processing is temporarily rate-limited. KnowledgeGPT will retry automatically.'
                if failure.code == 'provider_rate_limited' else 'AI processing is temporarily unavailable. KnowledgeGPT will retry automatically.')
        await db.commit()


async def process_document_async(self: Task, document_id: str) -> None:
    settings = get_settings()
    provider = None
    stage = "download"
    start = time.monotonic()
    try:
        document = await _load_document(document_id)
        if document is None:
            raise DocumentProcessingError("Document was deleted or does not exist")
        if document.status in (DocumentStatus.COMPLETED, DocumentStatus.FAILED, DocumentStatus.PENDING):
            return
        if document.next_retry_at and document.next_retry_at > datetime.now(timezone.utc):
            return
        if not document.temp_storage_key:
            raise ProcessingFailure("upload_unavailable", "The uploaded object is unavailable. Upload the file again.")
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Never use a user-controlled path as a local destination.
            local_path = os.path.join(tmp_dir, "payload." + document.name.rsplit(".", 1)[-1].lower())
            try:
                download_to_path(settings=settings, key=document.temp_storage_key, destination_path=local_path)
                stage = "virus scan"
                scan_file(file_path=local_path, settings=settings)
            except (S3Error, VirusScanUnavailableError) as exc:
                if self.request.retries < settings.CELERY_TASK_MAX_RETRIES:
                    await _update_status(document_id, status=DocumentStatus.VIRUS_SCANNING,
                                         detail=f"Temporary {stage} failure. Retrying.", progress=5)
                    raise self.retry(exc=DocumentProcessingError(f"Temporary {stage} failure"),
                                     countdown=settings.CELERY_TASK_RETRY_BACKOFF_SECONDS,
                                     max_retries=settings.CELERY_TASK_MAX_RETRIES) from exc
                raise DocumentProcessingError(f"Could not complete {stage} after multiple attempts. Retry the upload.") from exc
            except VirusFoundError as exc:
                delete_object(settings=settings, key=document.temp_storage_key)
                raise ProcessingFailure("malware_detected", "File rejected: malware detected. Upload a different file.") from exc

            stage = "validation"
            await _update_status(document_id, status=DocumentStatus.EXTRACTING, detail=None, progress=20)
            result = validate_uploaded_file(file_path=local_path, filename=document.name,
                                           size_bytes=os.path.getsize(local_path), settings=settings)
            async with AsyncSessionLocal() as db:
                doc = await db.get(Document, uuid.UUID(document_id))
                if doc is None:
                    raise DocumentProcessingError("Document was deleted")
                doc.checksum = result.checksum_sha256
                await db.commit()

            stage = "extraction and embedding"
            provider = build_llm_provider(settings)
            async with AsyncSessionLocal() as db:
                count = await process_document_embeddings(
                    db, settings=settings, provider=provider, document_id=document.id,
                    local_file_path=local_path, on_progress=_update_status,
                )
                await db.commit()  # durability MUST precede deletion of the original
            stage = "cleanup"
            if delete_object(settings=settings, key=document.temp_storage_key):
                async with AsyncSessionLocal() as db:
                    doc = await db.get(Document, uuid.UUID(document_id))
                    if doc:
                        doc.temp_storage_key = None
                        await db.commit()
            logger.info("document=%s task=%s provider=%s model=%s chunks=%d duration=%.2f stage=completed",
                        document_id, self.request.id, settings.LLM_PROVIDER.value,
                        settings.LLM_EMBEDDING_MODEL, count, time.monotonic() - start)
    except Retry:
        raise
    except Exception as exc:
        if stage == "cleanup":
            # Vectors are already committed. Keep the key for lifecycle cleanup.
            logger.error("document=%s stage=cleanup category=%s", document_id, type(exc).__name__)
            return
        failure = classify(exc, stage)
        if isinstance(exc, EmbeddingPipelineError):
            failure = ProcessingFailure('embedding_failure', 'Embedding generation failed. Retry Processing or contact support.', retryable=True)
        if isinstance(exc, LLMProviderError) and failure.retryable:
            current = await _load_document(document_id)
            attempts = (current.automatic_retries or 0) if current else settings.CELERY_TASK_MAX_RETRIES
            delay = retry_delay(attempts, settings.CELERY_TASK_RETRY_BACKOFF_SECONDS, getattr(exc,'retry_after',None))
            if attempts < settings.CELERY_TASK_MAX_RETRIES and self.request.retries < settings.CELERY_TASK_MAX_RETRIES and delay <= 3600:
                await _record_failure(document_id, failure, delay)
                raise self.retry(exc=DocumentProcessingError(failure.code), countdown=delay,
                                 max_retries=settings.CELERY_TASK_MAX_RETRIES) from None
        detail = str(failure)
        logger.error("document=%s task=%s stage=%s category=%s duration=%.2f",
                     document_id, self.request.id, stage, type(exc).__name__, time.monotonic() - start)
        await _fail(document_id, detail)
        await _record_failure(document_id, failure)
        raise DocumentProcessingError(detail) from None
    finally:
        if provider:
            await provider.aclose()


async def _process_locked(self: Task, document_id: str) -> None:
    # A transaction-scoped advisory lock serializes duplicate broker deliveries
    # without holding the document row lock (status updates need that row).
    lock_id = int.from_bytes(hashlib.sha256(document_id.encode()).digest()[:8], "big", signed=True)
    async with AsyncSessionLocal() as guard:
        locked = await guard.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id})
        if locked:
            await process_document_async(self, document_id)


_task_settings = get_settings()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.document_processing.process_document",
    soft_time_limit=_task_settings.CELERY_TASK_SOFT_TIME_LIMIT,
    time_limit=_task_settings.CELERY_TASK_TIME_LIMIT,
)
def process_document(self: Task, document_id: str) -> None:
    async def _run_and_cleanup() -> None:
        try:
            await _process_locked(self, document_id)
        finally:
            await dispose_engine()
    asyncio.run(_run_and_cleanup())


async def reconcile_stalled_documents_async(*, now: datetime | None = None) -> None:
    """Mark abandoned jobs retryable after the worker process has released its lock."""
    from sqlalchemy import select

    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    cutoff = now-timedelta(seconds=settings.CELERY_TASK_TIME_LIMIT*2)
    async with AsyncSessionLocal() as db:
        ids = list((await db.scalars(select(Document.id).where(
            Document.status.notin_([DocumentStatus.COMPLETED,DocumentStatus.FAILED]),
            Document.updated_at < cutoff).limit(100))).all())
    for doc_id in ids:
        key = int.from_bytes(hashlib.sha256(str(doc_id).encode()).digest()[:8], 'big', signed=True)
        async with AsyncSessionLocal() as db:
            if not await db.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key':key}):
                continue  # active worker owns this document, even if slow
            doc = await db.get(Document,doc_id,with_for_update=True)
            if not doc or doc.status in (DocumentStatus.COMPLETED,DocumentStatus.FAILED):
                continue
            if doc.next_retry_at and doc.next_retry_at > now:
                continue
            doc.status = DocumentStatus.FAILED
            doc.error_code = 'processing_timeout'
            doc.last_error_code = doc.error_code
            doc.last_error_at = now
            doc.next_retry_at = None
            doc.retryable = bool(doc.confirmed_at and doc.temp_storage_key)
            doc.status_detail = ('Processing stopped before completion. Retry Processing to resume saved batches.'
                if doc.retryable else 'Upload did not complete. Upload the file again.')
            await db.commit()


@celery_app.task(name="app.workers.tasks.document_processing.reconcile_stalled_documents")
def reconcile_stalled_documents() -> None:
    """Recover abandoned uploads and jobs killed before Python cleanup ran."""
    async def _run_and_cleanup() -> None:
        try:
            await reconcile_stalled_documents_async()
        finally:
            await dispose_engine()
    asyncio.run(_run_and_cleanup())
