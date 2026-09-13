from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chat import ChatSession
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge_base import CreateKnowledgeBaseRequest, KnowledgeBaseStats, UpdateKnowledgeBaseRequest


class KnowledgeBaseServiceError(Exception):
    pass


class KnowledgeBaseNotFoundError(KnowledgeBaseServiceError):
    pass


async def create_knowledge_base(
    db: AsyncSession, *, owner_id: uuid.UUID, body: CreateKnowledgeBaseRequest
) -> KnowledgeBase:
    await db.scalar(select(User).where(User.id == owner_id).with_for_update())
    count = await db.scalar(select(func.count(KnowledgeBase.id)).where(KnowledgeBase.owner_id == owner_id))
    if count >= get_settings().MAX_KNOWLEDGE_BASES_PER_USER:
        raise HTTPException(429, "Knowledge base limit reached")
    if body.parent_folder_id:
        await get_owned_knowledge_base(db, kb_id=body.parent_folder_id, owner_id=owner_id)
    kb = KnowledgeBase(
        owner_id=owner_id,
        parent_folder_id=body.parent_folder_id,
        name=body.name,
        description=body.description,
        color=body.color,
        icon=body.icon,
        tags=body.tags,
        is_folder=body.is_folder,
    )
    db.add(kb)
    await db.flush()
    return kb


async def get_owned_knowledge_base(db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID) -> KnowledgeBase:
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == owner_id))
    if not kb:
        raise KnowledgeBaseNotFoundError("Knowledge base not found")
    return kb


async def list_knowledge_bases(
    db: AsyncSession, *, owner_id: uuid.UUID, include_archived: bool = False, search: str | None = None
) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase).where(KnowledgeBase.owner_id == owner_id)
    if not include_archived:
        stmt = stmt.where(KnowledgeBase.is_archived == False)  # noqa: E712
    if search:
        stmt = stmt.where(KnowledgeBase.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(KnowledgeBase.updated_at.desc())
    return list((await db.scalars(stmt)).all())


async def update_knowledge_base(
    db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID, body: UpdateKnowledgeBaseRequest
) -> KnowledgeBase:
    kb = await get_owned_knowledge_base(db, kb_id=kb_id, owner_id=owner_id)
    update_data = body.model_dump(exclude_unset=True)
    if update_data.get("parent_folder_id"):
        if update_data["parent_folder_id"] == kb_id:
            raise HTTPException(400, "A folder cannot contain itself")
        await get_owned_knowledge_base(db, kb_id=update_data["parent_folder_id"], owner_id=owner_id)
    for field, value in update_data.items():
        setattr(kb, field, value)
    await db.flush()
    return kb


async def archive_knowledge_base(db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID) -> KnowledgeBase:
    kb = await get_owned_knowledge_base(db, kb_id=kb_id, owner_id=owner_id)
    kb.is_archived = True
    await db.flush()
    return kb


async def delete_knowledge_base(db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    kb = await get_owned_knowledge_base(db, kb_id=kb_id, owner_id=owner_id)
    # Cascades to documents -> document_chunks and chat_sessions -> chat_messages
    # via the FK ondelete="CASCADE" defined in the initial migration.
    await db.delete(kb)


async def duplicate_knowledge_base(db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID) -> KnowledgeBase:
    """Duplicates the knowledge base's metadata (name, tags, color/icon) as
    an empty new KB. Does NOT copy documents/chunks — re-processing
    documents under the new KB is a deliberate choice (avoids duplicating
    embeddings and gives the copy a clean slate), consistent with "Duplicate"
    meaning "start a new one styled the same way" rather than "clone data."
    """
    source = await get_owned_knowledge_base(db, kb_id=kb_id, owner_id=owner_id)
    return await create_knowledge_base(db, owner_id=owner_id, body=CreateKnowledgeBaseRequest(
        name=f"{source.name} (copy)",
        description=source.description,
        color=source.color,
        icon=source.icon,
        tags=list(source.tags) if source.tags else None,
    ))


async def get_knowledge_base_stats(db: AsyncSession, *, kb_id: uuid.UUID, owner_id: uuid.UUID) -> KnowledgeBaseStats:
    kb = await get_owned_knowledge_base(db, kb_id=kb_id, owner_id=owner_id)

    status_rows = (
        await db.execute(
            select(Document.status, func.count(Document.id))
            .where(Document.knowledge_base_id == kb_id)
            .group_by(Document.status)
        )
    ).all()
    documents_by_status = {status.value: count for status, count in status_rows}

    chat_session_count = await db.scalar(
        select(func.count(ChatSession.id)).where(ChatSession.knowledge_base_id == kb_id)
    ) or 0

    return KnowledgeBaseStats(
        document_count=kb.document_count,
        total_chunk_count=kb.total_chunk_count,
        chat_session_count=chat_session_count,
        storage_bytes_used=kb.storage_bytes_used,
        documents_by_status=documents_by_status,
    )
