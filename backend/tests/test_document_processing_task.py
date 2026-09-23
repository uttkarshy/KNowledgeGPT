import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from billiard.exceptions import SoftTimeLimitExceeded
from celery.exceptions import MaxRetriesExceededError, Retry

from app.core.aws import S3Error
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.workers.tasks import document_processing as dp
from app.workers.tasks.document_processing import (
    DocumentProcessingError,
    process_document,
    reconcile_stalled_documents_async,
)


@pytest.fixture(autouse=True)
def isolated_task_lock(monkeypatch):
    # Unit tests exercise the task lifecycle; PostgreSQL lock needs the integration gate.
    async def direct(task, document_id):
        return await dp.process_document_async(task, document_id)
    monkeypatch.setattr(dp, "_process_locked", direct)
    monkeypatch.setattr(dp, "dispose_engine", AsyncMock())
    monkeypatch.setattr(dp, "_record_failure", AsyncMock())


def _fake_document(doc_id: str) -> Document:
    return Document(
        id=doc_id, name="test.pdf", file_type=FileType.PDF,
        temp_storage_key="fake/key.pdf", status=DocumentStatus.VIRUS_SCANNING,
    )


def test_task_routes_to_the_queue_the_worker_actually_consumes():
    """Regression test for the root cause: task_routes must route this
    task to the same queue name the worker container is bound to
    (docker-compose.yml's celery-worker command uses -Q document_processing).
    If this ever silently reverts, the whole upload pipeline breaks again
    with no error, just documents stuck forever."""
    from app.workers.celery_app import celery_app

    route = celery_app.amqp.router.route({}, process_document.name)
    assert route["queue"].name == "document_processing"


def test_document_task_has_explicit_soft_and_hard_limits():
    from app.core.config import get_settings

    settings = get_settings()
    assert process_document.soft_time_limit == settings.CELERY_TASK_SOFT_TIME_LIMIT
    assert process_document.time_limit == settings.CELERY_TASK_TIME_LIMIT


def test_retry_exhaustion_marks_document_failed():
    """Regression test: once max_retries is exceeded, the document must be
    marked FAILED with a clear reason, never left stuck at its last status."""
    doc_id = str(uuid.uuid4())
    fake_doc = _fake_document(doc_id)
    captured = []

    async def fake_update_status(document_id, *, status, detail, progress):
        captured.append((status, detail, progress))

    async def fake_load_document(document_id):
        return fake_doc

    def fake_retry_exhausted(exc=None, **kwargs):
        raise MaxRetriesExceededError()

    with patch.object(dp, "_load_document", fake_load_document), \
         patch.object(dp, "_update_status", fake_update_status), \
         patch.object(process_document, "retry", fake_retry_exhausted), \
         patch("app.workers.tasks.document_processing.download_to_path", side_effect=S3Error("persistent outage")):
        with pytest.raises(DocumentProcessingError):
            process_document.run(doc_id)

    assert captured[-1][0] == DocumentStatus.FAILED
    status, detail, progress = captured[-1]
    assert status == DocumentStatus.FAILED
    assert "download" in detail.lower()
    assert progress == 0


def test_in_progress_retry_does_not_prematurely_mark_failed():
    """Regression test: while retries remain, Retry must propagate normally
    (so Celery schedules the next attempt) and the document must NOT be
    marked FAILED yet."""
    doc_id = str(uuid.uuid4())
    fake_doc = _fake_document(doc_id)
    captured = []

    async def fake_update_status(document_id, *, status, detail, progress):
        captured.append((status, detail, progress))

    async def fake_load_document(document_id):
        return fake_doc

    def fake_retry_still_retrying(exc=None, **kwargs):
        raise Retry(exc=exc)

    with patch.object(dp, "_load_document", fake_load_document), \
         patch.object(dp, "_update_status", fake_update_status), \
         patch.object(process_document, "retry", fake_retry_still_retrying), \
         patch("app.workers.tasks.document_processing.download_to_path", side_effect=S3Error("transient blip")):
        try:
            process_document.run(doc_id)
            raise AssertionError("expected Retry to propagate")
        except Retry:
            pass

    assert all(item[0] != DocumentStatus.FAILED for item in captured)


def test_unanticipated_exception_is_caught_by_outer_safety_net():
    """Regression test: even an exception type nobody anticipated must
    still result in FAILED, never a silent stuck document."""
    doc_id = str(uuid.uuid4())
    fake_doc = _fake_document(doc_id)
    captured = []

    class SomeUnexpectedError(Exception):
        pass

    async def fake_update_status(document_id, *, status, detail, progress):
        captured.append((status, detail, progress))

    async def fake_load_document(document_id):
        return fake_doc

    with patch.object(dp, "_load_document", fake_load_document), \
         patch.object(dp, "_update_status", fake_update_status), \
         patch("app.workers.tasks.document_processing.download_to_path", side_effect=SomeUnexpectedError("bug")):
        with pytest.raises(DocumentProcessingError):
            process_document.run(doc_id)

    assert len(captured) == 1
    status, detail, _progress = captured[0]
    assert status == DocumentStatus.FAILED
    assert "unexpected" in detail.lower()


@pytest.mark.asyncio
async def test_soft_timeout_marks_document_failed_and_retryable(monkeypatch):
    doc_id = str(uuid.uuid4())
    fake_doc = _fake_document(doc_id)
    fake_doc.owner_id = uuid.uuid4()
    fake_doc.knowledge_base_id = uuid.uuid4()
    fake_doc.name = "pathological.pdf"
    updates = []
    failures = []

    async def fake_update_status(document_id, *, status, detail, progress):
        updates.append((status, detail, progress))

    async def fake_record_failure(document_id, failure, delay=None):
        failures.append((failure, delay))

    def fake_download(*, destination_path, **_kwargs):
        with open(destination_path, "wb") as file:
            file.write(b"%PDF-1.7 synthetic")

    db = AsyncMock()
    db.get.return_value = fake_doc

    class SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return False

    provider = SimpleNamespace(aclose=AsyncMock())
    monkeypatch.setattr(dp, "_load_document", AsyncMock(return_value=fake_doc))
    monkeypatch.setattr(dp, "_update_status", fake_update_status)
    monkeypatch.setattr(dp, "_record_failure", fake_record_failure)
    monkeypatch.setattr(dp, "AsyncSessionLocal", SessionContext)
    monkeypatch.setattr(dp, "download_to_path", fake_download)
    monkeypatch.setattr(dp, "scan_file", lambda **_kwargs: None)
    monkeypatch.setattr(dp, "validate_uploaded_file", lambda **_kwargs: SimpleNamespace(checksum_sha256="a" * 64))
    monkeypatch.setattr(dp, "build_llm_provider", lambda _settings: provider)
    monkeypatch.setattr(dp, "process_document_embeddings", AsyncMock(side_effect=SoftTimeLimitExceeded()))

    with pytest.raises(DocumentProcessingError, match="time budget"):
        await dp.process_document_async(process_document, doc_id)

    assert updates[-1][0] == DocumentStatus.FAILED
    assert failures[-1][0].code == "processing_timeout"
    assert failures[-1][0].retryable is True
    provider.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconciliation_marks_unlocked_stalled_document_retryable(monkeypatch):
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    doc = SimpleNamespace(
        status=DocumentStatus.EXTRACTING,
        confirmed_at=now,
        temp_storage_key="saved/pathological.pdf",
        next_retry_at=None,
    )
    lookup_db = AsyncMock()
    lookup_db.scalars.return_value = SimpleNamespace(all=lambda: [doc_id])
    update_db = AsyncMock()
    update_db.scalar.return_value = True
    update_db.get.return_value = doc
    sessions = iter([lookup_db, update_db])

    class SessionContext:
        def __init__(self):
            self.db = next(sessions)

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(dp, "AsyncSessionLocal", SessionContext)
    await reconcile_stalled_documents_async(now=now)

    assert doc.status == DocumentStatus.FAILED
    assert doc.error_code == "processing_timeout"
    assert doc.retryable is True
    assert "Retry Processing" in doc.status_detail
    update_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconciliation_cannot_mutate_a_document_while_active_lock_is_held(monkeypatch):
    doc_id = uuid.uuid4()
    lookup_db = AsyncMock()
    lookup_db.scalars.return_value = SimpleNamespace(all=lambda: [doc_id])
    lock_db = AsyncMock()
    lock_db.scalar.return_value = False
    sessions = iter([lookup_db, lock_db])

    class SessionContext:
        def __init__(self):
            self.db = next(sessions)

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(dp, "AsyncSessionLocal", SessionContext)
    await reconcile_stalled_documents_async(now=datetime.now(timezone.utc))

    lock_db.get.assert_not_awaited()
    lock_db.commit.assert_not_awaited()
