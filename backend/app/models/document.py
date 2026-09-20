from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import DocumentStatus, FileType


class Document(Base, UUIDPKMixin, TimestampMixin):
    """Represents an uploaded document's METADATA ONLY.

    Per the storage rules: the original file lives in S3 only transiently
    during processing and is deleted once embedding generation succeeds.
    This row (plus its DocumentChunk children) is the sole permanent record.
    """

    __tablename__ = "documents"
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    automatic_retries: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    provider_rate_limit_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(512), nullable=False)

    file_type: Mapped[FileType] = mapped_column(
        Enum(
            FileType,
            name="file_type",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
    )  # e.g. "en", "hi", "en+hi"

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )

    status_detail: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )  # error message if FAILED

    processing_progress_pct: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )  # sha256 of original file

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    original_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # S3 key while the file is transiently present during processing.
    # Set back to NULL once the original is deleted post-embedding.
    temp_storage_key: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )

    # Free-form structured metadata extracted during processing
    # (author, source URL, custom tags, OCR engine used, etc.)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(  # noqa: F821
        back_populates="documents"
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(  # noqa: F821
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )  # noqa: F821