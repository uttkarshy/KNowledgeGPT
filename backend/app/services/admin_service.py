from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.models.enums import AuditAction, MessageRole
from app.models.knowledge_base import KnowledgeBase
from app.models.usage import ApiUsageLog, AuditLog
from app.models.user import User
from app.schemas.admin import AnalyticsSummary


class AdminServiceError(Exception):
    pass


class UserNotFoundError(AdminServiceError):
    pass


class CannotModifySelfError(AdminServiceError):
    pass


async def list_users(
    db: AsyncSession, *, search: str | None = None, role: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[User], int]:
    stmt = select(User)
    count_stmt = select(func.count(User.id))

    if search:
        clause = User.email.ilike(f"%{search}%")
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    users = list((await db.scalars(stmt)).all())
    return users, total


async def get_user_detail(db: AsyncSession, *, user_id: uuid.UUID) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise UserNotFoundError("User not found")

    kb_count = await db.scalar(select(func.count(KnowledgeBase.id)).where(KnowledgeBase.owner_id == user_id)) or 0
    doc_count = await db.scalar(select(func.count(Document.id)).where(Document.owner_id == user_id)) or 0
    storage = await db.scalar(
        select(func.coalesce(func.sum(KnowledgeBase.storage_bytes_used), 0)).where(KnowledgeBase.owner_id == user_id)
    ) or 0

    return {
        "user": user,
        "knowledge_base_count": kb_count,
        "document_count": doc_count,
        "total_storage_bytes": storage,
    }


async def suspend_user(db: AsyncSession, *, admin_id: uuid.UUID, user_id: uuid.UUID) -> User:
    if admin_id == user_id:
        raise CannotModifySelfError("Admins cannot suspend their own account")
    user = await db.get(User, user_id)
    if not user:
        raise UserNotFoundError("User not found")
    user.is_suspended = True
    await db.flush()

    db.add(AuditLog(user_id=admin_id, action=AuditAction.SUSPEND_USER, resource_type="user", resource_id=str(user_id)))
    return user


async def unsuspend_user(db: AsyncSession, *, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise UserNotFoundError("User not found")
    user.is_suspended = False
    await db.flush()
    return user


async def delete_user(db: AsyncSession, *, admin_id: uuid.UUID, user_id: uuid.UUID) -> None:
    if admin_id == user_id:
        raise CannotModifySelfError("Admins cannot delete their own account")
    user = await db.get(User, user_id)
    if not user:
        raise UserNotFoundError("User not found")

    db.add(AuditLog(user_id=admin_id, action=AuditAction.DELETE_USER, resource_type="user", resource_id=str(user_id)))
    # Cascades to knowledge_bases -> documents -> document_chunks and
    # chat_sessions -> chat_messages -> chat_citations via FK ondelete="CASCADE".
    await db.delete(user)


async def get_analytics_summary(db: AsyncSession) -> AnalyticsSummary:
    total_users = await db.scalar(select(func.count(User.id))) or 0
    total_kbs = await db.scalar(select(func.count(KnowledgeBase.id))) or 0
    total_docs = await db.scalar(select(func.count(Document.id))) or 0
    total_chunks = await db.scalar(select(func.coalesce(func.sum(KnowledgeBase.total_chunk_count), 0))) or 0
    total_sessions = await db.scalar(select(func.count(ChatSession.id))) or 0
    total_storage = await db.scalar(select(func.coalesce(func.sum(KnowledgeBase.storage_bytes_used), 0))) or 0

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    api_calls_24h = await db.scalar(select(func.count(ApiUsageLog.id)).where(ApiUsageLog.created_at >= since)) or 0
    api_errors_24h = await db.scalar(
        select(func.count(ApiUsageLog.id)).where(ApiUsageLog.created_at >= since, ApiUsageLog.status_code >= 400)
    ) or 0

    status_rows = (await db.execute(select(Document.status, func.count(Document.id)).group_by(Document.status))).all()
    documents_by_status = {status.value: count for status, count in status_rows}

    week = datetime.now(timezone.utc) - timedelta(days=7)
    signups = await db.scalar(select(func.count(User.id)).where(User.created_at >= week)) or 0
    questions = await db.scalar(select(func.count(ChatMessage.id)).where(
        ChatMessage.role == MessageRole.USER, ChatMessage.created_at >= week)) or 0
    quota = await db.scalar(select(func.coalesce(func.sum(Document.provider_rate_limit_count), 0))) or 0
    errors = (await db.execute(select(Document.last_error_code, func.count(Document.id)).where(
        Document.last_error_at >= week, Document.last_error_code.is_not(None)
    ).group_by(Document.last_error_code))).all()
    return AnalyticsSummary(
        recent_signups_7d=signups, questions_7d=questions, embedding_429_count=quota,
        recent_processing_errors=dict(errors),
        total_users=total_users,
        total_knowledge_bases=total_kbs,
        total_documents=total_docs,
        total_chunks=total_chunks,
        total_chat_sessions=total_sessions,
        total_storage_bytes=total_storage,
        api_calls_last_24h=api_calls_24h,
        api_errors_last_24h=api_errors_24h,
        documents_by_status=documents_by_status,
    )


async def get_api_usage_logs(db: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[ApiUsageLog]:
    stmt = select(ApiUsageLog).order_by(ApiUsageLog.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


async def get_error_logs(db: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[ApiUsageLog]:
    stmt = (
        select(ApiUsageLog)
        .where(ApiUsageLog.status_code >= 400)
        .order_by(ApiUsageLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.scalars(stmt)).all())


async def get_audit_logs(db: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())
