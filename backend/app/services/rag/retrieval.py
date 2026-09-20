"""
Retrieval: pgvector cosine similarity search with mandatory tenant-isolation
filtering (knowledge_base_id + owner_id are never optional — every query is
scoped to exactly one user's exactly one knowledge base) plus optional
metadata filters (specific documents, language, date range).

Uses pgvector's `cosine_distance` comparator (maps to the `<=>` operator,
which the HNSW index built in the database migration is defined against).
Distance is converted to similarity (`1 - distance`) in Python after
fetching candidates — filtering in SQL on a derived expression would
prevent the index from being used efficiently, so we over-fetch top_k and
threshold-filter afterward instead.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    page_number: int | None
    section: str | None
    similarity: float
    structure: dict | None = None


@dataclass
class RetrievalFilters:
    document_ids: list[uuid.UUID] | None = None
    language: str | None = None
    uploaded_after: datetime | None = None
    uploaded_before: datetime | None = None


async def similarity_search(
    db: AsyncSession,
    *,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    query_embedding: list[float],
    embedding_model: str,
    top_k: int = 8,
    min_similarity: float = 0.72,
    filters: RetrievalFilters | None = None,
) -> list[RetrievedChunk]:
    """Returns up to `top_k` chunks with similarity >= min_similarity,
    ordered by similarity descending. Returns an empty list if nothing
    clears the threshold — callers (the RAG engine) treat that as "no
    answer available" per the never-hallucinate rule, rather than lowering
    the bar to force a result.
    """
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.content,
            DocumentChunk.page_number,
            DocumentChunk.section,
            DocumentChunk.structure,
            Document.name.label("document_name"),
            DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.knowledge_base_id == knowledge_base_id,
            DocumentChunk.owner_id == owner_id,  # belt-and-suspenders tenant isolation
            Document.owner_id == owner_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.status == DocumentStatus.COMPLETED,
            DocumentChunk.embedding_model == embedding_model,
        )
    )

    if filters:
        if filters.document_ids is not None:
            stmt = stmt.where(DocumentChunk.document_id.in_(filters.document_ids))
        if filters.language:
            stmt = stmt.where(Document.language == filters.language)
        if filters.uploaded_after:
            stmt = stmt.where(Document.created_at >= filters.uploaded_after)
        if filters.uploaded_before:
            stmt = stmt.where(Document.created_at <= filters.uploaded_before)

    # Over-fetch candidates so the Python-side similarity threshold has
    # something to filter from without needing a second round trip.
    stmt = stmt.order_by("distance").limit(max(top_k * 3, top_k))

    rows = (await db.execute(stmt)).all()

    results: list[RetrievedChunk] = []
    for row in rows:
        similarity = 1.0 - float(row.distance)
        if similarity < min_similarity:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                document_name=row.document_name,
                content=row.content,
                page_number=row.page_number,
                section=row.section,
                similarity=similarity,
                structure=getattr(row, "structure", None),
            )
        )
        if len(results) >= top_k:
            break

    return results
