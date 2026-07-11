from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.knowledge_base import KnowledgeBase


class ChatServiceError(Exception):
    pass


class KnowledgeBaseNotFoundError(ChatServiceError):
    pass


class SessionNotFoundError(ChatServiceError):
    pass


async def create_session(
    db: AsyncSession, *, owner_id: uuid.UUID, knowledge_base_id: uuid.UUID, title: str | None
) -> ChatSession:
    kb = await db.scalar(
        select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == owner_id)
    )
    if not kb:
        raise KnowledgeBaseNotFoundError("Knowledge base not found or not owned by this user")

    session = ChatSession(owner_id=owner_id, knowledge_base_id=knowledge_base_id, title=title or "New Chat")
    db.add(session)
    await db.flush()
    return session


async def get_owned_session(db: AsyncSession, *, session_id: uuid.UUID, owner_id: uuid.UUID) -> ChatSession:
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == owner_id)
    )
    if not session:
        raise SessionNotFoundError("Chat session not found")
    return session


async def list_sessions(
    db: AsyncSession, *, owner_id: uuid.UUID, knowledge_base_id: uuid.UUID | None = None
) -> list[ChatSession]:
    stmt = select(ChatSession).where(ChatSession.owner_id == owner_id, ChatSession.is_archived == False)  # noqa: E712
    if knowledge_base_id:
        stmt = stmt.where(ChatSession.knowledge_base_id == knowledge_base_id)
    stmt = stmt.order_by(ChatSession.is_pinned.desc(), ChatSession.updated_at.desc())
    return list((await db.scalars(stmt)).all())


async def get_messages(db: AsyncSession, *, session_id: uuid.UUID, owner_id: uuid.UUID) -> list[ChatMessage]:
    # Ownership check first (raises if not owned), then fetch messages with
    # citations eagerly loaded so the API response doesn't trigger N+1
    # lazy-loads on an async session (which would error outside a greenlet).
    await get_owned_session(db, session_id=session_id, owner_id=owner_id)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .options(selectinload(ChatMessage.citations))
        .order_by(ChatMessage.created_at)
    )
    return list((await db.scalars(stmt)).all())
