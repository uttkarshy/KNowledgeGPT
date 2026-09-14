"""Exercise real request cleanup and telemetry FK locks with a bounded pool."""
import asyncio
import os
import uuid

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.usage import ApiUsageLog
from app.models.user import User

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL")


@pytest.mark.asyncio
async def test_request_transactions_finish_before_usage_logging(monkeypatch):
    from app.core import usage_logging
    from app.db import session
    from app.main import app

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=2)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(session, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(usage_logging, "AsyncSessionLocal", sessions)
    user_id = uuid.uuid4()
    try:
        async with sessions() as db:
            db.add(User(id=user_id, email=f"pool-{user_id}@example.com", hashed_password="unused"))
            await db.commit()
        token = create_access_token(user_id=user_id, role="user", settings=settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                    headers={"Authorization": f"Bearer {token}"}) as client:
            # Creation locks the user FOR UPDATE; telemetry needs a conflicting
            # FK key-share lock. The old middleware deadlocks on the first call.
            for index in range(25):
                response = await asyncio.wait_for(client.post("/api/knowledge-bases", json={"name": f"pool {index}"}), 5)
                assert response.status_code == 201, response.text
                assert engine.pool.checkedout() == 0
                response = await client.delete(f"/api/knowledge-bases/{response.json()['id']}")
                assert response.status_code == 204
                assert engine.pool.checkedout() == 0
            for _ in range(5):
                responses = await asyncio.wait_for(asyncio.gather(*(client.get("/api/auth/me") for _ in range(25))), 10)
                assert all(r.status_code == 200 for r in responses)
                assert engine.pool.checkedout() == 0
        async with sessions() as db:
            assert await db.scalar(select(func.count()).select_from(ApiUsageLog).where(ApiUsageLog.user_id == user_id)) == 175
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()
