from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import enforce_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import (
    ConfirmUploadRequest,
    DocumentPublic,
    DocumentStatusResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_url(
    body: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Step 1 of upload: register a PENDING document row and return a
    presigned S3 PUT URL. The client uploads the file bytes directly to S3,
    then calls POST /confirm."""
    await enforce_limit(settings, key=f"uploads:{current_user.id}", limit=settings.RATE_LIMIT_UPLOADS_PER_DAY, seconds=86400)
    await enforce_limit(settings, key="uploads_global", limit=settings.RATE_LIMIT_GLOBAL_UPLOADS_PER_DAY, seconds=86400)
    try:
        document, upload_url = await document_service.create_upload_url(
            db,
            settings=settings,
            owner_id=current_user.id,
            knowledge_base_id=body.knowledge_base_id,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    except document_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except document_service.DocumentServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return UploadUrlResponse(
        document_id=document.id,
        upload_url=upload_url,
        s3_key=document.temp_storage_key,
        expires_in=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
    )


@router.post("/confirm", response_model=DocumentStatusResponse)
async def confirm_upload(
    body: ConfirmUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Step 2 of upload: client confirms the S3 PUT finished. We verify the
    object actually exists (never trust the client alone) and enqueue
    background processing."""
    try:
        document = await document_service.confirm_upload_and_enqueue(
            db, settings=settings, document_id=body.document_id, owner_id=current_user.id
        )
    except document_service.DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except document_service.UploadNotFoundInS3Error as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except document_service.DocumentServiceError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        status_detail=document.status_detail,
        processing_progress_pct=document.processing_progress_pct,
        error_code=document.error_code,
        retryable=document.retryable,
        next_retry_at=document.next_retry_at,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Polled by the frontend upload progress UI."""
    try:
        document = await document_service.get_owned_document(db, document_id=document_id, owner_id=current_user.id)
    except document_service.DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        status_detail=document.status_detail,
        processing_progress_pct=document.processing_progress_pct,
        error_code=document.error_code,
        retryable=document.retryable,
        next_retry_at=document.next_retry_at,
    )


@router.get("", response_model=list[DocumentPublic])
async def list_documents(
    knowledge_base_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(
        db, owner_id=current_user.id, knowledge_base_id=knowledge_base_id
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        await document_service.delete_document(
            db, settings=settings, document_id=document_id, owner_id=current_user.id
        )
    except document_service.DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/limits")
async def upload_limits(
    _user: User = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    return {"max_size_bytes": settings.MAX_UPLOAD_SIZE_BYTES,
            "max_pdf_pages": settings.MAX_PDF_PAGES,
            "allowed_extensions": sorted(settings.ALLOWED_FILE_EXTENSIONS)}


@router.post("/{document_id}/retry", response_model=DocumentPublic)
async def retry_document(
    document_id: uuid.UUID, current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings),
):
    await enforce_limit(settings, key=f"processing_retry:{current_user.id}", limit=10, seconds=3600)
    await enforce_limit(settings, key="processing_retry_global", limit=200, seconds=3600)
    try:
        return await document_service.retry_processing(
            db, settings=settings, document_id=document_id, owner_id=current_user.id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except document_service.DocumentServiceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
