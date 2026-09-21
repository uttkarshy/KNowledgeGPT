import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.enums import UserRole
from app.services import document_service
from app.services.processing_errors import classify
from app.services.upload.validation import FileValidationError, validate_size


def test_limits_are_authenticated_and_use_configured_values():
    client = TestClient(app)
    assert client.get("/api/documents/limits").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[get_settings] = lambda: Settings(MAX_PDF_PAGES=37, MAX_UPLOAD_SIZE_BYTES=1048576)
    try:
        response = client.get("/api/documents/limits")
        assert response.status_code == 200
        assert response.json()["max_pdf_pages"] == 37
        assert response.json()["max_size_bytes"] == 1048576
        assert set(response.json()) == {"max_pdf_pages", "max_size_bytes", "allowed_extensions", "credits_per_page"}
    finally:
        app.dependency_overrides.clear()


def test_retry_endpoint_enforces_owner_and_admin_metrics_reject_regular_user(monkeypatch):
    owner, doc = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=owner, role=UserRole.USER)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    retry = AsyncMock(side_effect=document_service.DocumentNotFoundError("Document not found"))
    monkeypatch.setattr(document_service, "retry_processing", retry)
    monkeypatch.setattr("app.api.documents.enforce_limit", AsyncMock())
    try:
        client = TestClient(app)
        assert client.post(f"/api/documents/{doc}/retry").status_code == 404
        assert retry.call_args.kwargs["owner_id"] == owner
        assert client.get("/api/admin/analytics").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_size_failure_is_typed():
    try:
        validate_size(2048, Settings(MAX_UPLOAD_SIZE_BYTES=1024))
    except FileValidationError as exc:
        assert classify(exc, "validation").code == "file_too_large"
    else:
        raise AssertionError("Oversized upload accepted")
