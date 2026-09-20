"""Stored JSONB header propagation and authorization with real PostgreSQL."""

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.rag.exact_date import DateEvidenceLimit
from app.services.rag.exhaustive import calculate, evidence
from app.services.rag.query_router import route
from app.services.rag.retrieval import RetrievalFilters
from tests.test_structured_financial import QUESTION, table

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL/pgvector")


async def test_stored_generic_tables_preserve_header_scope_and_authorization():
    settings = Settings()
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, other = uuid.uuid4(), uuid.uuid4()
    kb, other_kb, foreign_kb = (uuid.uuid4() for _ in range(3))
    doc_ids = [uuid.uuid4() for _ in range(4)]
    fixture = table()
    try:
        async with sessions() as db:
            db.add_all([User(id=u, email=f"headers-{u}@example.com") for u in (owner, other)])
            await db.flush()
            db.add_all(
                [
                    KnowledgeBase(id=k, owner_id=u, name="Synthetic")
                    for k, u in ((kb, owner), (other_kb, owner), (foreign_kb, other))
                ]
            )
            await db.flush()
            scopes = [
                (owner, kb, DocumentStatus.COMPLETED),
                (owner, other_kb, DocumentStatus.COMPLETED),
                (other, foreign_kb, DocumentStatus.COMPLETED),
                (owner, kb, DocumentStatus.EXTRACTING),
            ]
            for doc_id, (user, knowledge_base, status) in zip(doc_ids, scopes, strict=True):
                db.add(
                    Document(
                        id=doc_id,
                        owner_id=user,
                        knowledge_base_id=knowledge_base,
                        name="same-name.pdf",
                        file_type=FileType.PDF,
                        status=status,
                        checksum="a" * 64,
                    )
                )
            await db.flush()
            for doc_id, (user, knowledge_base, _) in zip(doc_ids, scopes, strict=True):
                for index, row in enumerate(fixture):
                    db.add(
                        DocumentChunk(
                            document_id=doc_id,
                            owner_id=user,
                            knowledge_base_id=knowledge_base,
                            chunk_index=index,
                            content=row.content,
                            page_number=row.page_number,
                            structure=row.structure,
                            embedding=[1.0] + [0.0] * 1535,
                            embedding_model=settings.LLM_EMBEDDING_MODEL,
                            checksum="b" * 64,
                        )
                    )
            await db.commit()
            rows = await evidence(db, owner_id=owner, kb_id=kb)
            assert [c.chunk_index for c in rows] == list(range(len(fixture)))
            assert rows[0].structure == fixture[0].structure
            assert {c.document_id for c in rows} == {doc_ids[0]}
            answer, sources = calculate(rows, route(QUESTION), QUESTION)
            assert "Analyzed 4 complete debit rows" in answer and "820.00" in answer
            assert [c.chunk_id for c in sources] == [rows[i].chunk_id for i in (3, 4, 1)]
            assert await evidence(db, owner_id=other, kb_id=kb) == []
            assert await evidence(db, owner_id=owner, kb_id=foreign_kb) == []
            assert (
                await evidence(db, owner_id=owner, kb_id=kb, filters=RetrievalFilters(document_ids=[doc_ids[1]])) == []
            )
            assert await evidence(db, owner_id=owner, kb_id=kb, filters=RetrievalFilters(document_ids=[])) == []
            # Move the schema out of scope: authorized data rows must never
            # borrow a header from a foreign owner or knowledge base.
            continuation = await db.get(DocumentChunk, rows[0].chunk_id)
            for attribute, foreign_value, original in (("owner_id", other, owner), ("knowledge_base_id", other_kb, kb)):
                setattr(continuation, attribute, foreign_value)
                await db.flush()
                incomplete = await evidence(db, owner_id=owner, kb_id=kb)
                assert len(incomplete) == len(fixture) - 1
                with pytest.raises(DateEvidenceLimit):
                    calculate(incomplete, route(QUESTION), QUESTION)
                setattr(continuation, attribute, original)
                await db.flush()
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id.in_([owner, other])))
            await db.commit()
        await engine.dispose()
