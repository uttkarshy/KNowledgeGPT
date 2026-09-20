from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import MessageRole


class ChatSession(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "chat_sessions"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(512), default="New Chat", nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    share_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)  # set when shared

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base, UUIDPKMixin, TimestampMixin):
    """A single message. Supports branching via parent_message_id: editing a
    user message creates a sibling branch rather than mutating history."""

    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=True
    )

    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role", values_callable=lambda e: [v.value for v in e]), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Populated for assistant messages only
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    is_active_branch: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    citations: Mapped[list["ChatCitation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan",
        order_by="(ChatCitation.source_index.asc().nullslast(), ChatCitation.created_at, ChatCitation.id)"
    )


class ChatCitation(Base, UUIDPKMixin, TimestampMixin):
    """One citation attached to an assistant message — always document +
    page + chunk + similarity score, per the "never answer without citing"
    rule enforced in the RAG engine."""

    __tablename__ = "chat_citations"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )

    source_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    document_name: Mapped[str] = mapped_column(String(512), nullable=False)  # denormalized for display speed
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)

    message: Mapped["ChatMessage"] = relationship(back_populates="citations")
