"""Real async DB regression for estimate response serialization and confirmation."""

import os
import uuid
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.document import DocumentPublic

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL")


@pytest.mark.parametrize("extension,pages", [("txt", None), ("pdf", 3)])
async def test_estimate_serializes_complete_response_and_upload_can_proceed(monkeypatch, extension, pages):
    from app.api import documents
    from app.core import usage_logging
    from app.db import session
    from app.main import app
    from app.services import document_service
    from app.workers.tasks.document_processing import process_document

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(session, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(usage_logging, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(documents, "enforce_limit", AsyncMock())
    monkeypatch.setattr(document_service, "generate_presigned_put_url", lambda **kw: "https://storage.test/upload")
    if extension == "pdf":
        import fitz

        with fitz.open() as pdf:
            for _ in range(pages):
                pdf.new_page()
            content = pdf.tobytes()
    else:
        content = b"Estimate regression document"

    def download(**kwargs):
        from pathlib import Path

        Path(kwargs["destination_path"]).write_bytes(content)

    monkeypatch.setattr(document_service, "head_object_size", lambda **kw: len(content))
    monkeypatch.setattr(document_service, "download_to_path", download)
    enqueue = Mock()
    monkeypatch.setattr(process_document, "delay", enqueue)
    user_id, kb_id = uuid.uuid4(), uuid.uuid4()
    try:
        async with sessions() as db:
            db.add(User(id=user_id, email=f"estimate-{user_id}@example.com", credit_balance=100))
            await db.flush()
            db.add(KnowledgeBase(id=kb_id, owner_id=user_id, name="Estimate regression"))
            await db.commit()
        token = create_access_token(user_id=user_id, role="user", settings=settings)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            upload = await client.post("/api/documents/upload-url", json={
                "knowledge_base_id": str(kb_id), "filename": f"estimate.{extension}",
                "content_type": "application/pdf" if extension == "pdf" else "text/plain",
                "size_bytes": len(content),
            })
            assert upload.status_code == 201, upload.text
            document_id = upload.json()["document_id"]
            # ASGITransport raises ResponseValidationError on the unfixed code:
            # the real UPDATE expires updated_at before FastAPI serializes it.
            estimate = await client.post(f"/api/documents/{document_id}/estimate")
            assert estimate.status_code == 200, estimate.text
            body = estimate.json()
            assert set(body) == set(DocumentPublic.model_fields)
            parsed = DocumentPublic.model_validate(body)
            assert parsed.updated_at is not None
            assert parsed.updated_at >= parsed.created_at
            assert parsed.page_count == pages
            assert parsed.estimated_credits == (pages or 1) * settings.DOCUMENT_CREDITS_PER_PAGE
            assert parsed.status.value == "pending"
            enqueue.assert_not_called()
            # A new session sees the committed estimate after request teardown.
            async with sessions() as db:
                stored = await db.get(Document, uuid.UUID(document_id))
                assert DocumentPublic.model_validate(stored).model_dump(mode="json") == body
                assert (await db.get(User, user_id)).credit_balance == 100
            confirm = await client.post("/api/documents/confirm", json={"document_id": document_id})
            assert confirm.status_code == 200, confirm.text
            assert confirm.json()["status"] == "virus_scanning"
            assert confirm.json()["processing_progress_pct"] == 5
            enqueue.assert_called_once_with(document_id)
            async with sessions() as db:
                stored = await db.get(Document, uuid.UUID(document_id))
                assert stored.confirmed_at is not None
                assert stored.status.value == "virus_scanning"
                assert (await db.get(User, user_id)).credit_balance == 100
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()
