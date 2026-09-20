from __future__ import annotations

import uuid
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

# The pgvector column dimension is fixed at table-definition time and MUST
# match settings.LLM_EMBEDDING_DIMENSIONS for whichever embedding model is
# configured. Changing embedding models to one with a different dimension
# requires a migration (see alembic/versions/0002_change_embedding_dim.py.example).
_EMBEDDING_DIM = 1536  # schema contract; changing this requires an explicit migration and re-embedding


class DocumentChunk(Base, UUIDPKMixin, TimestampMixin):
    """A single semantically-chunked passage of a document, with its embedding.

    This table (plus its vector index) is what every similarity search in
    the RAG engine queries against. Nothing about the original file is kept
    here beyond what's needed to render a citation back to the user.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # every similarity query filters by knowledge_base_id first
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # belt-and-suspenders tenant isolation, enforced again at query time
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # order within document
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # nearest heading/section title

    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)

    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 of chunk content, for dedupe

    document: Mapped["Document"] = relationship(back_populates="chunks")  # noqa: F821
