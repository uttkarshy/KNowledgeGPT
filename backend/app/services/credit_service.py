from __future__ import annotations

import inspect
import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import ApiUsageLog
from app.models.user import User


class InsufficientCreditsError(Exception):
    pass


async def charge(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    credits: int,
    operation: str,
    idempotency_key: str,
    model: str | None = None,
    metadata: dict | None = None,
) -> bool:
    """Atomically charge once. Returns False when this exact charge already exists."""
    if credits < 0:
        raise ValueError("credits must be non-negative")
    statement = insert(ApiUsageLog).values(
        user_id=user_id,
        endpoint=operation,
        operation=operation,
        model=model,
        credits_delta=-credits,
        idempotency_key=idempotency_key,
        usage_metadata=metadata,
        status_code=200,
    ).on_conflict_do_nothing(index_elements=[ApiUsageLog.idempotency_key]).returning(ApiUsageLog.id)
    inserted = await db.scalar(statement)
    if inserted is None:
        return False
    changed = await db.execute(
        update(User)
        .where(User.id == user_id, User.credit_balance >= credits)
        .values(credit_balance=User.credit_balance - credits)
        .returning(User.credit_balance)
    )
    balance = changed.scalar_one_or_none()
    if inspect.isawaitable(balance):  # supports lightweight async DB test doubles
        balance = await balance
    if balance is None:
        await db.rollback()
        raise InsufficientCreditsError(f"This operation needs {credits} credits.")
    return True


async def refund(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    credits: int,
    operation: str,
    idempotency_key: str,
    metadata: dict | None = None,
) -> bool:
    statement = insert(ApiUsageLog).values(
        user_id=user_id,
        endpoint=operation,
        operation=operation,
        credits_delta=credits,
        idempotency_key=idempotency_key,
        usage_metadata=metadata,
        status_code=200,
    ).on_conflict_do_nothing(index_elements=[ApiUsageLog.idempotency_key]).returning(ApiUsageLog.id)
    if await db.scalar(statement) is None:
        return False
    await db.execute(update(User).where(User.id == user_id).values(credit_balance=User.credit_balance + credits))
    return True


async def grant(
    db: AsyncSession, *, user_id: uuid.UUID, credits: int, operation: str,
    idempotency_key: str, metadata: dict | None = None,
) -> bool:
    return await refund(
        db, user_id=user_id, credits=credits, operation=operation,
        idempotency_key=idempotency_key, metadata=metadata,
    )


async def recent_usage(db: AsyncSession, *, user_id: uuid.UUID, limit: int = 20) -> list[ApiUsageLog]:
    rows = await db.scalars(
        select(ApiUsageLog)
        .where(ApiUsageLog.user_id == user_id, ApiUsageLog.operation.is_not(None))
        .order_by(ApiUsageLog.created_at.desc())
        .limit(limit)
    )
    return list(rows.all())
