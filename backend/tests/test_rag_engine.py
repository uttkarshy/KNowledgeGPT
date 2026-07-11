import uuid
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.models.chat import ChatSession
from app.schemas.llm import EmbeddingResult, LLMStreamChunk, LLMUsage
from app.services.rag import engine as engine_module
from app.services.rag.retrieval import RetrievedChunk


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


async def _no_history(db, *, session_id, limit=10):
    return []


@pytest.mark.asyncio
async def test_llm_is_never_called_when_nothing_clears_similarity_threshold():
    """The single most safety-critical test in this codebase: if retrieval
    finds nothing sufficiently similar, the LLM must never be invoked."""

    class ProviderThatMustNotBeCalled:
        async def embed(self, request):
            return EmbeddingResult(embeddings=[[0.1, 0.2, 0.3, 0.4]], model="fake", dimensions=4, usage=LLMUsage())

        async def stream(self, request):
            raise AssertionError("LLM must never be called when no chunks clear the similarity threshold")
            yield  # pragma: no cover

    async def _empty_search(db, **kwargs):
        return []

    settings = get_settings()
    fake_session = ChatSession(id=uuid.uuid4(), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4(), title="Test")
    db = _FakeSession()

    with patch.object(engine_module, "_fetch_recent_history", _no_history), \
         patch.object(engine_module, "similarity_search", _empty_search):
        events = [
            e
            async for e in engine_module.answer_question(
                db, settings=settings, provider=ProviderThatMustNotBeCalled(),
                session=fake_session, question="What is our confidential merger plan?",
            )
        ]

    assert len(events) == 1
    assert events[0].type == "no_answer"
    assert events[0].delta == settings.RAG_NO_ANSWER_MESSAGE
    assert events[0].confidence == 0.0


@pytest.mark.asyncio
async def test_successful_answer_streams_and_generates_accurate_citations():
    settings = get_settings()
    doc_id = uuid.uuid4()
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(), document_id=doc_id, document_name="Q3 Report.pdf",
        content="Revenue grew 12 percent year over year.", page_number=4, section="Financials", similarity=0.89,
    )

    class FakeProvider:
        async def embed(self, request):
            return EmbeddingResult(embeddings=[[0.1, 0.2, 0.3, 0.4]], model="fake", dimensions=4, usage=LLMUsage())

        async def stream(self, request):
            assert any("Revenue grew 12 percent" in m.content for m in request.messages)
            for word in ["Revenue ", "grew ", "12 percent ", "according to [1]."]:
                yield LLMStreamChunk(delta=word)
            yield LLMStreamChunk(done=True, usage=LLMUsage(input_tokens=120, output_tokens=15, total_tokens=135))

    async def _one_chunk_search(db, **kwargs):
        return [chunk]

    fake_session = ChatSession(id=uuid.uuid4(), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4(), title="Test")
    db = _FakeSession()

    with patch.object(engine_module, "_fetch_recent_history", _no_history), \
         patch.object(engine_module, "similarity_search", _one_chunk_search):
        events = [
            e
            async for e in engine_module.answer_question(
                db, settings=settings, provider=FakeProvider(),
                session=fake_session, question="What was our revenue growth?",
            )
        ]

    deltas = [e.delta for e in events if e.type == "delta"]
    done_events = [e for e in events if e.type == "done"]

    assert "".join(deltas) == "Revenue grew 12 percent according to [1]."
    assert len(done_events) == 1
    assert done_events[0].confidence == 0.89
    assert done_events[0].citations[0]["document_name"] == "Q3 Report.pdf"
    assert done_events[0].citations[0]["page_number"] == 4
    assert done_events[0].citations[0]["similarity_score"] == 0.89
