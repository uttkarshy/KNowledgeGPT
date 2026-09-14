import re
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings
from app.models.chat import ChatSession
from app.schemas.llm import EmbeddingResult, LLMStreamChunk, LLMUsage
from app.services.rag import engine, exact_date
from app.services.rag.retrieval import RetrievalFilters, RetrievedChunk


def statement():
    doc = uuid.uuid4()
    return [SimpleNamespace(id=uuid.uuid4(), document_id=doc, document_name='Statement.pdf', chunk_index=i,
                            page_number=i + 1, section=None, content=content)
            for i, content in enumerate([
                'Date | Reference | Debit | Credit\n31 Jul 2026 | A | Debit 1000.00',
                '31/07/2026 | B | Debit 406.89',
                'Statement continuation header',
                '31-Jul-26 | C | Debit 309.00',
                '01 Aug 2026 | D | Credit 50.00',
            ])]


def database(rows):
    db = AsyncMock()
    db.execute.side_effect = [SimpleNamespace(one=lambda: (len(rows), sum(len(r.content) for r in rows))),
                             SimpleNamespace(all=lambda: rows)]
    return db


@pytest.mark.parametrize('text', ['31 jul 2026', 'July 31, 2026', '2026-07-31', '31/07/2026'])
def test_explicit_dates(text):
    assert exact_date.explicit_date('total on ' + text) == date(2026, 7, 31)


@pytest.mark.parametrize('text', ['03/04/2026', '31 Feb 2026', '31 Jul 2026 and 1 Aug 2026', '31 Jul 26', 'on 31/07'])
def test_unsafe_date_scope_refuses_partial_answer(text):
    with pytest.raises(exact_date.DateEvidenceLimit):
        exact_date.explicit_date(text)


def test_ordinary_query_keeps_semantic_path():
    assert exact_date.explicit_date('What is our policy?') is None


async def test_first_answer_includes_all_pages_beyond_vector_top_k(monkeypatch):
    rows = statement()
    db = database(rows)
    db.add = lambda obj: None
    db.flush = AsyncMock()
    monkeypatch.setattr(engine, '_fetch_recent_history', AsyncMock(return_value=[]))
    semantic = [RetrievedChunk(rows[0].id, rows[0].document_id, 'Statement.pdf', rows[0].content, 1, None, .9)]
    monkeypatch.setattr(engine, 'similarity_search', AsyncMock(return_value=semantic))

    class Provider:
        async def embed(self, request):
            return EmbeddingResult(embeddings=[[.1] * 1536], dimensions=1536, model='gemini-embedding-001', usage=LLMUsage())

        async def stream(self, request):
            # Deterministic generation oracle: only amounts actually delivered
            # in the first prompt count. A top-K-only implementation gives 1000.
            prompt = request.messages[-1].content
            amounts = [Decimal(v) for v in re.findall(r'Debit (\d+\.\d{2})', prompt)]
            total = sum(amounts)
            assert total == Decimal('1715.89')
            yield LLMStreamChunk(delta=f'{total:.2f} [1] [2] [4]')

    session = ChatSession(id=uuid.uuid4(), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4())
    events = [event async for event in engine.answer_question(db, settings=get_settings(), provider=Provider(),
              session=session, question='calculate how much did i spent on 31 jul 2026')]
    assert events[-1].type == 'done'
    assert '1715.89' in events[0].delta
    assert {c['page_number'] for c in events[-1].citations} >= {1, 2, 4}
    engine.similarity_search.assert_awaited_once()


async def test_date_sql_isolation_and_filters():
    rows = statement()
    db = database(rows)
    owner, kb, document = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await exact_date.exact_date_evidence(db, target=date(2026, 7, 31), owner_id=owner, knowledge_base_id=kb,
                                       filters=RetrievalFilters(document_ids=[document], language='en'))
    for call in db.execute.call_args_list:
        compiled = call.args[0].compile(dialect=postgresql.dialect())
        sql = str(compiled)
        for column in ['document_chunks.owner_id', 'documents.owner_id', 'document_chunks.knowledge_base_id',
                       'documents.knowledge_base_id', 'documents.status', 'documents.language', 'document_chunks.document_id IN']:
            assert column in sql
        assert owner in compiled.params.values() and kb in compiled.params.values()
        assert [document] in compiled.params.values()


async def test_matching_context_overflow_fails_closed():
    rows = statement()
    rows[0].content += ' evidence' * 10000
    with pytest.raises(exact_date.DateEvidenceLimit, match='smaller document set'):
        await exact_date.exact_date_evidence(database(rows), target=date(2026, 7, 31), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4())


async def test_scan_limit_stops_before_fetching_contents():
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(one=lambda: (exact_date.MAX_SCAN_CHUNKS + 1, 100))
    with pytest.raises(exact_date.DateEvidenceLimit):
        await exact_date.exact_date_evidence(db, target=date(2026, 7, 31), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4())
    assert db.execute.await_count == 1


async def test_limit_returns_persisted_clarification_without_generation(monkeypatch):
    db = AsyncMock()
    db.add = lambda obj: None
    monkeypatch.setattr(engine, '_fetch_recent_history', AsyncMock(return_value=[]))
    monkeypatch.setattr(engine, 'exact_date_evidence', AsyncMock(side_effect=exact_date.DateEvidenceLimit(exact_date.LIMIT_MESSAGE)))
    provider = AsyncMock()
    session = ChatSession(id=uuid.uuid4(), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4())
    events = [e async for e in engine.answer_question(db, settings=get_settings(), provider=provider, session=session, question='total on 31 Jul 2026')]
    assert events[0].type == 'no_answer' and 'smaller document set' in events[0].delta
    provider.embed.assert_not_called()
    provider.stream.assert_not_called()
