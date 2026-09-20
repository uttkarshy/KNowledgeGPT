from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class AdminUserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    is_suspended: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserDetailPublic(AdminUserPublic):
    knowledge_base_count: int
    document_count: int
    total_storage_bytes: int


class AnalyticsSummary(BaseModel):
    total_users: int
    total_knowledge_bases: int
    total_documents: int
    total_chunks: int
    total_chat_sessions: int
    total_storage_bytes: int
    api_calls_last_24h: int
    api_errors_last_24h: int
    documents_by_status: dict[str, int]
    recent_signups_7d: int = 0
    questions_7d: int = 0
    embedding_429_count: int = 0
    recent_processing_errors: dict[str, int] = {}


class ApiUsageLogPublic(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    endpoint: str
    model: Optional[str] = None
    input_tokens: int
    output_tokens: int
    latency_ms: Optional[int] = None
    status_code: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogPublic(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
