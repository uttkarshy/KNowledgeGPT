from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=32)
    icon: Optional[str] = Field(default=None, max_length=64)
    tags: Optional[list[str]] = None
    parent_folder_id: Optional[uuid.UUID] = None
    is_folder: bool = False


class UpdateKnowledgeBaseRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[list[str]] = None
    is_archived: Optional[bool] = None


class KnowledgeBasePublic(BaseModel):
    id: uuid.UUID
    parent_folder_id: Optional[uuid.UUID] = None
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[list[str]] = None
    is_archived: bool
    is_folder: bool
    document_count: int
    total_chunk_count: int
    storage_bytes_used: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseStats(BaseModel):
    document_count: int
    total_chunk_count: int
    chat_session_count: int
    storage_bytes_used: int
    documents_by_status: dict[str, int]
