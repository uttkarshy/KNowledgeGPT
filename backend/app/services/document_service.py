from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aws import S3Error, build_upload_key, generate_presigned_put_url, head_object_size
from app.core.config import Settings
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.models.knowledge_base import KnowledgeBase


class DocumentServiceError(Exception):
    pass


class KnowledgeBaseNotFoundError(DocumentServiceError):
    pass


class DocumentNotFoundError(DocumentServiceError):
    pass


class UploadNotFoundInS3Error(DocumentServiceError):
    pass


_EXTENSION_TO_FILE_TYPE = {
    "pdf": FileType.PDF, "docx": FileType.DOCX, "doc": FileType.DOC, "txt": FileType.TXT,
    "csv": FileType.CSV, "xlsx": FileType.XLSX, "xls": FileType.XLS, "pptx": FileType.PPTX,
    "md": FileType.MARKDOWN, "markdown": FileType.MARKDOWN, "html": FileType.HTML,
    "htm": FileType.HTML, "xml": FileType.XML, "json": FileType.JSON, "rtf": FileType.RTF,
    "png": FileType.IMAGE, "jpg": FileType.IMAGE, "jpeg": FileType.IMAGE, "tiff": FileType.IMAGE,
    "bmp": FileType.IMAGE, "zip": FileType.ZIP,
}


async def _get_owned_knowledge_base(db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID) -> KnowledgeBase:
    kb = await db.scalar(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == owner_id)
    )
    if not kb:
        raise KnowledgeBaseNotFoundError("Knowledge base not found or not owned by this user")
    return kb


async def create_upload_url(
    db: AsyncSession,
    *,
    settings: Settings,
    owner_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    filename: str,
    content_type: str,
    size_bytes: int,
) -> tuple[Document, str]:
    """Creates a PENDING document row and returns (document, presigned_put_url).

    The row exists before the file is even uploaded — this is what lets the
    client's later /confirm call be a simple lookup rather than needing to
    pass all the metadata again, and it's what the admin dashboard/upload
    progress UI polls against from the very first moment.
    """
    await _get_owned_knowledge_base(db, kb_id=knowledge_base_id, owner_id=owner_id)

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_FILE_EXTENSIONS:
        raise DocumentServiceError(
            f"Extension '.{ext}' is not allowed. Allowed: {', '.join(sorted(settings.ALLOWED_FILE_EXTENSIONS))}"
        )
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise DocumentServiceError(
            f"File size {size_bytes} bytes exceeds the {settings.MAX_UPLOAD_SIZE_BYTES} byte limit"
        )

    document = Document(
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        name=filename,
        file_type=_EXTENSION_TO_FILE_TYPE.get(ext, FileType.TXT),
        status=DocumentStatus.PENDING,
        checksum="",  # populated after download+validation in the worker
        original_size_bytes=size_bytes,
    )
    db.add(document)
    await db.flush()  # populate document.id for the S3 key

    s3_key = build_upload_key(
        settings=settings, owner_id=str(owner_id), document_id=str(document.id), filename=filename
    )
    document.temp_storage_key = s3_key

    try:
        url = generate_presigned_put_url(settings=settings, key=s3_key, content_type=content_type)
    except S3Error as e:
        raise DocumentServiceError(str(e)) from e

    return document, url


async def get_owned_document(db: AsyncSession, *, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
    doc = await db.scalar(
        select(Document).where(Document.id == document_id, Document.owner_id == owner_id)
    )
    if not doc:
        raise DocumentNotFoundError("Document not found")
    return doc


async def confirm_upload_and_enqueue(
    db: AsyncSession, *, settings: Settings, document_id: uuid.UUID, owner_id: uuid.UUID
) -> Document:
    """Verifies the object actually landed in S3 (never trust the client's
    say-so), updates status, and enqueues the Celery processing task."""
    document = await get_owned_document(db, document_id=document_id, owner_id=owner_id)

    if document.status != DocumentStatus.PENDING:
        raise DocumentServiceError(f"Document is already in status '{document.status.value}'")

    try:
        actual_size = head_object_size(settings=settings, key=document.temp_storage_key)
    except S3Error as e:
        raise UploadNotFoundInS3Error(
            f"Could not find the uploaded file in storage — did the upload complete? ({e})"
        ) from e

    document.original_size_bytes = actual_size
    document.status = DocumentStatus.VIRUS_SCANNING
    document.processing_progress_pct = 5
    await db.flush()

    # Imported lazily to avoid FastAPI process needing Celery's broker
    # connection at import time (keeps `uvicorn app.main:app` fast to boot).
    from app.workers.tasks.document_processing import process_document

    process_document.delay(str(document.id))
    return document


async def list_documents(
    db: AsyncSession, *, owner_id: uuid.UUID, knowledge_base_id: Optional[uuid.UUID] = None
) -> list[Document]:
    stmt = select(Document).where(Document.owner_id == owner_id)
    if knowledge_base_id:
        stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
    stmt = stmt.order_by(Document.created_at.desc())
    result = await db.scalars(stmt)
    return list(result.all())


async def delete_document(db: AsyncSession, *, settings: Settings, document_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    from app.core.aws import delete_object

    document = await get_owned_document(db, document_id=document_id, owner_id=owner_id)
    if document.temp_storage_key:
        delete_object(settings=settings, key=document.temp_storage_key)
    await db.delete(document)  # cascades to document_chunks via FK ondelete
