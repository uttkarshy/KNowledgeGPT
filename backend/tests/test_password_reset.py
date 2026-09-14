import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_token
from app.models.user import User
from app.services.auth.service import (
    InvalidOrExpiredTokenError,
    confirm_password_reset,
    issue_token_pair,
    rotate_refresh_token,
)


async def test_old_access_token_rejected_new_epoch_accepted():
    user = User(id=uuid.uuid4(), token_version=1, is_active=True, is_suspended=False)
    db = AsyncMock()
    db.get.return_value = user
    settings = get_settings()
    old = create_access_token(user_id=user.id, role='user', settings=settings)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=old), db, settings)
    assert exc.value.status_code == 401
    new = create_access_token(user_id=user.id, role='user', settings=settings, token_version=1)
    assert await get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=new), db, settings) is user


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL')
async def test_password_reset_revokes_access_and_refresh_and_allows_new_login():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    try:
        async with sessions() as db:
            user = User(id=user_id, email=f'reset-{user_id}@example.com', password_reset_token=hash_token('reset-secret'),
                        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
            db.add(user)
            await db.flush()
            old = await issue_token_pair(db, user=user, settings=settings, user_agent=None, ip_address=None)
            await db.commit()
        async with sessions() as db:
            await confirm_password_reset(db, token='reset-secret', new_password='NewSecurePassword!123')
            await db.commit()
        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=old.access_token), db, settings)
            assert exc.value.status_code == 401
            await db.rollback()
            with pytest.raises(InvalidOrExpiredTokenError):
                await rotate_refresh_token(db, settings=settings, plaintext_refresh_token=old.refresh_token, user_agent=None, ip_address=None)
            await db.rollback()
            from app.services.auth.service import authenticate_user
            user = await authenticate_user(db, email=f'reset-{user_id}@example.com', password='NewSecurePassword!123')
            new = await issue_token_pair(db, user=user, settings=settings, user_agent=None, ip_address=None)
            await db.commit()
            assert (await get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=new.access_token), db, settings)).id == user_id
            rotated = await rotate_refresh_token(db, settings=settings, plaintext_refresh_token=new.refresh_token, user_agent=None, ip_address=None)
            await db.commit()
            assert rotated.access_token != new.access_token
            with pytest.raises(InvalidOrExpiredTokenError):
                await confirm_password_reset(db, token='reset-secret', new_password='AnotherSecurePassword!123')
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()
