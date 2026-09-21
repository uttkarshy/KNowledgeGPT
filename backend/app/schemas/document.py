from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus, FileType


class UploadUrlRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0, description="Client-reported size; re-validated server-side after upload.")


class UploadUrlResponse(BaseModel):
    document_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in: int


class ConfirmUploadRequest(BaseModel):
    document_id: uuid.UUID


class DocumentPublic(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    name: str
    file_type: FileType
    language: Optional[str] = None
    status: DocumentStatus
    status_detail: Optional[str] = None
    error_code: Optional[str] = None
    retryable: bool = False
    next_retry_at: Optional[datetime] = None
    processing_progress_pct: int
    page_count: Optional[int] = None
    processed_page_count: int = 0
    estimated_credits: Optional[int] = None
    chunk_count: int
    original_size_bytes: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    status: DocumentStatus
    status_detail: Optional[str] = None
    error_code: Optional[str] = None
    retryable: bool = False
    next_retry_at: Optional[datetime] = None
    processing_progress_pct: int
    page_count: Optional[int] = None
    processed_page_count: int = 0
    estimated_credits: Optional[int] = None
