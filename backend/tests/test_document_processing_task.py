import uuid
from unittest.mock import AsyncMock, patch

import pytest
from celery.exceptions import MaxRetriesExceededError, Retry

from app.core.aws import S3Error
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.workers.tasks import document_processing as dp
from app.workers.tasks.document_processing import DocumentProcessingError, process_document


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
