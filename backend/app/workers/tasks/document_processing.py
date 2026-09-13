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

from celery import Task
from celery.exceptions import Retry
from sqlalchemy import text

from app.core.aws import S3Error, delete_object, download_to_path
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, dispose_engine
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.embedding.pipeline import EmbeddingPipelineError, process_document_embeddings
from app.services.llm.factory import build_llm_provider
from app.services.upload.validation import FileValidationError, validate_uploaded_file
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


async def process_document_async(self: Task, document_id: str) -> None:
    settings = get_settings()
    provider = None
    stage = "download"
    start = time.monotonic()
    try:
        document = await _load_document(document_id)
        if document is None:
            raise DocumentProcessingError("Document was deleted or does not exist")
        if document.status == DocumentStatus.COMPLETED:
            return
        if not document.temp_storage_key:
            raise DocumentProcessingError("Upload is unavailable. Upload the document again.")
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
                raise DocumentProcessingError("File rejected: malware detected") from exc

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
        if isinstance(exc, (DocumentProcessingError, FileValidationError, EmbeddingPipelineError)):
            detail = str(exc)
        else:
            detail = f"Unexpected processing error during {stage}. Please retry or contact support."
        logger.error("document=%s task=%s stage=%s category=%s duration=%.2f",
                     document_id, self.request.id, stage, type(exc).__name__, time.monotonic() - start)
        await _fail(document_id, detail)
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


@celery_app.task(bind=True, name="app.workers.tasks.document_processing.process_document")
def process_document(self: Task, document_id: str) -> None:
    async def _run_and_cleanup() -> None:
        try:
            await _process_locked(self, document_id)
        finally:
            await dispose_engine()
    asyncio.run(_run_and_cleanup())


@celery_app.task(name="app.workers.tasks.document_processing.reconcile_stalled_documents")
def reconcile_stalled_documents() -> None:
    """Recover abandoned uploads and jobs killed before Python cleanup ran."""
    async def reconcile():
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import update
        settings = get_settings()
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.CELERY_TASK_TIME_LIMIT * 2)
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(update(Document).where(
                    Document.status.notin_([DocumentStatus.COMPLETED, DocumentStatus.FAILED]),
                    Document.updated_at < cutoff,
                ).values(status=DocumentStatus.FAILED, processing_progress_pct=0,
                         status_detail="Upload or processing timed out. Delete this entry and upload the file again."))
                await db.commit()
        finally:
            await dispose_engine()
    asyncio.run(reconcile())
