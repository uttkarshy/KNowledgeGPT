from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MessageRole


class CreateSessionRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    title: Optional[str] = Field(default=None, max_length=512)


class ChatSessionPublic(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    is_pinned: bool
    is_archived: bool
    is_bookmarked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CitationPublic(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    similarity_score: float
    excerpt: str

    model_config = {"from_attributes": True}


class ChatMessagePublic(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    model_used: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    confidence_score: Optional[float] = None
    citations: list[CitationPublic] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    document_ids: Optional[list[uuid.UUID]] = Field(default=None, max_length=100)
    language: Optional[str] = Field(default=None, max_length=16)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value.encode("utf-8")) > 1800:
            raise ValueError("Question must contain text and be at most 1800 UTF-8 bytes")
        return value
