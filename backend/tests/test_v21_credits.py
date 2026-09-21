import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.main import app
from app.models.usage import ApiUsageLog
from app.models.user import User
from app.services import credit_service


def test_razorpay_webhook_rejects_invalid_signature():
    app.dependency_overrides[get_settings] = lambda: Settings(RAZORPAY_WEBHOOK_SECRET="unit-secret")
    try:
        response = TestClient(app).post(
            "/api/billing/razorpay/webhook", content=b'{}', headers={"x-razorpay-signature": "bad"}
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_credit_summary_preserves_starter_user():
    user = SimpleNamespace(credit_balance=100, plan_code="starter")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings] = lambda: Settings(STARTER_CREDITS=100)
    try:
        response = TestClient(app).get("/api/billing/credits")
        assert response.status_code == 200
        assert response.json()["balance"] == 100
        assert response.json()["payments_enabled"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL")
async def test_atomic_concurrent_and_idempotent_credit_deductions():
    settings = Settings()
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    try:
        async with sessions() as db:
            db.add(User(id=user_id, email=f"credits-{user_id}@example.com", credit_balance=1))
            await db.commit()

        async def spend(key: str):
            async with sessions() as db:
                try:
                    result = await credit_service.charge(
                        db, user_id=user_id, credits=1, operation="test.spend", idempotency_key=key
                    )
                    await db.commit()
                    return result
                except credit_service.InsufficientCreditsError:
                    return "insufficient"

        import asyncio
        outcomes = await asyncio.gather(spend("concurrent-a"), spend("concurrent-b"))
        assert sorted(map(str, outcomes)) == ["True", "insufficient"]
        async with sessions() as db:
            user = await db.get(User, user_id)
            assert user.credit_balance == 0
            assert await credit_service.charge(
                db, user_id=user_id, credits=1, operation="test.spend", idempotency_key="concurrent-a"
            ) is False
            await db.commit()
            user = await db.get(User, user_id)
            assert user.credit_balance == 0
            assert len(list((await db.scalars(select(ApiUsageLog).where(
                ApiUsageLog.user_id == user_id, ApiUsageLog.credits_delta == -1
            ))).all())) == 1
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()
