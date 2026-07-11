from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ARRAY, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class KnowledgeBase(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "knowledge_bases"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)   # hex or design-token name
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)    # lucide icon name
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(64)), nullable=True)

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_folder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Denormalized counters, maintained by the upload/embedding pipeline —
    # avoids COUNT(*) over documents/chunks on every dashboard load.
    document_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_chunk_count: Mapped[int] = mapped_column(default=0, nullable=False)
    storage_bytes_used: Mapped[int] = mapped_column(default=0, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="knowledge_bases")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    children: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    parent: Mapped[Optional["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="children",
        remote_side="KnowledgeBase.id",
    )
