"""
Document processing pipeline (Celery task).

Current scope (Upload Service increment):
    download from S3 -> virus scan -> file validation -> checksum

Chunking and embedding are intentionally left as a clearly-marked next step
for the Embedding Service increment — this task hands off to it by leaving
the document in CHUNKING status with the local temp file's checksum/
metadata already recorded. The original file is deliberately NOT deleted
from S3 yet: per the storage rule, deletion only happens after embedding
succeeds, which this increment doesn't yet perform.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from celery import Task

from app.core.aws import S3Error, delete_object, download_to_path
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.upload.validation import FileValidationError, validate_uploaded_file
from app.services.upload.virus_scan import VirusFoundError, VirusScanUnavailableError, scan_file
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Celery tasks are synchronous; each task run gets its own event loop
    for the async DB session rather than sharing one across task invocations
    (which would be unsafe across worker process boundaries anyway)."""
    return asyncio.run(coro)


async def _update_status(document_id: str, *, status: DocumentStatus, detail: str | None, progress: int) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        if document is None:
            logger.warning("Document %s vanished during processing", document_id)
            return
        document.status = status
        document.status_detail = detail
        document.processing_progress_pct = progress
        await db.commit()


async def _load_document(document_id: str) -> Document | None:
    async with AsyncSessionLocal() as db:
        return await db.get(Document, document_id)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.document_processing.process_document",
    max_retries=3,
    default_retry_delay=30,
)
def process_document(self: Task, document_id: str) -> None:
    settings = get_settings()
    document = _run_async(_load_document(document_id))
    if document is None:
        logger.error("process_document called for nonexistent document %s", document_id)
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = os.path.join(tmp_dir, document.name)

        # ---------------- Download ----------------
        try:
            download_to_path(settings=settings, key=document.temp_storage_key, destination_path=local_path)
        except S3Error as e:
            logger.warning("Download failed for document %s: %s — retrying", document_id, e)
            raise self.retry(exc=e)

        # ---------------- Virus scan ----------------
        try:
            scan_file(file_path=local_path, settings=settings)
        except VirusFoundError as e:
            logger.warning("Malware detected in document %s: %s", document_id, e)
            delete_object(settings=settings, key=document.temp_storage_key)
            _run_async(
                _update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    detail=f"File rejected: malware detected ({e.signature})",
                    progress=0,
                )
            )
            return
        except VirusScanUnavailableError as e:
            logger.error("Virus scan unavailable for document %s: %s — retrying", document_id, e)
            raise self.retry(exc=e)

        _run_async(
            _update_status(document_id, status=DocumentStatus.EXTRACTING, detail=None, progress=20)
        )

        # ---------------- Validation ----------------
        try:
            result = validate_uploaded_file(
                file_path=local_path,
                filename=document.name,
                size_bytes=os.path.getsize(local_path),
                settings=settings,
            )
        except FileValidationError as e:
            logger.info("Validation failed for document %s: %s", document_id, e)
            delete_object(settings=settings, key=document.temp_storage_key)
            _run_async(
                _update_status(
                    document_id, status=DocumentStatus.FAILED, detail=f"Validation failed: {e}", progress=0
                )
            )
            return

        # ---------------- Chunking + embedding (real, not a stub) ----------------
        async def _run_embedding_pipeline():
            from app.services.llm.factory import get_llm_provider
            from app.services.embedding.pipeline import EmbeddingPipelineError, process_document_embeddings

            async with AsyncSessionLocal() as db:
                doc = await db.get(Document, document_id)
                doc.checksum = result.checksum_sha256
                doc.status = DocumentStatus.CHUNKING
                doc.status_detail = None
                doc.processing_progress_pct = 40
                await db.commit()

            provider = get_llm_provider()
            async with AsyncSessionLocal() as db:
                try:
                    chunk_count = await process_document_embeddings(
                        db,
                        settings=settings,
                        provider=provider,
                        document_id=document.id,
                        local_file_path=local_path,
                    )
                    await db.commit()
                    return chunk_count
                except EmbeddingPipelineError as e:
                    await db.rollback()
                    async with AsyncSessionLocal() as failure_db:
                        failed_doc = await failure_db.get(Document, document_id)
                        if failed_doc:
                            failed_doc.status = DocumentStatus.FAILED
                            failed_doc.status_detail = str(e)
                            failed_doc.processing_progress_pct = 0
                            await failure_db.commit()
                    raise

        try:
            chunk_count = _run_async(_run_embedding_pipeline())
        except Exception as e:
            logger.error("Embedding pipeline failed for document %s: %s", document_id, e)
            return

        logger.info(
            "Document %s fully processed: %d chunks embedded and stored, original deleted from S3",
            document_id, chunk_count,
        )
