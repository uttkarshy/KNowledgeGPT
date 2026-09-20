import os
import uuid
from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.rag.exact_date import exact_date_evidence
from app.services.rag.retrieval import RetrievalFilters
from tests.test_exact_date import statement


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL')
async def test_date_scan_real_postgres_all_pages_and_tenant_isolation():
    engine = create_async_engine(get_settings().DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, other = uuid.uuid4(), uuid.uuid4()
    kb, other_kb, foreign_kb = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    target_doc = uuid.uuid4()
    try:
        async with sessions() as db:
            db.add_all([User(id=u, email=f'date-{u}@example.com') for u in (owner, other)])
            await db.flush()
            db.add_all([KnowledgeBase(id=k, owner_id=u, name='date test') for k, u in [(kb, owner), (other_kb, owner), (foreign_kb, other)]])
            await db.flush()
            cases = [(target_doc, owner, kb, DocumentStatus.COMPLETED),
                     (uuid.uuid4(), owner, kb, DocumentStatus.COMPLETED),
                     (uuid.uuid4(), owner, other_kb, DocumentStatus.COMPLETED),
                     (uuid.uuid4(), other, foreign_kb, DocumentStatus.COMPLETED),
                     (uuid.uuid4(), owner, kb, DocumentStatus.FAILED)]
            for doc_id, user_id, knowledge_base_id, status in cases:
                db.add(Document(id=doc_id, owner_id=user_id, knowledge_base_id=knowledge_base_id,
                                name='Statement.pdf', file_type=FileType.PDF, status=status, checksum='a' * 64))
                await db.flush()
                for row in statement():
                    db.add(DocumentChunk(id=uuid.uuid4(), document_id=doc_id, owner_id=user_id,
                            knowledge_base_id=knowledge_base_id, chunk_index=row.chunk_index, content=row.content,
                            page_number=row.page_number, embedding=[1.0] + [0.0] * 1535, checksum='b' * 64, embedding_model='gemini-embedding-001'))
            await db.commit()
            evidence = await exact_date_evidence(db, target=date(2026, 7, 31), owner_id=owner, knowledge_base_id=kb,
                                                 filters=RetrievalFilters(document_ids=[target_doc]))
            assert {c.page_number for c in evidence} == {1, 2, 3, 4, 5}
            assert {c.document_id for c in evidence} == {target_doc}
            all_owned = await exact_date_evidence(db, target=date(2026, 7, 31), owner_id=owner, knowledge_base_id=kb)
            assert len({c.document_id for c in all_owned}) == 2
            assert await exact_date_evidence(db, target=date(2026, 7, 31), owner_id=other, knowledge_base_id=kb) == []
            assert await exact_date_evidence(db, target=date(2026, 7, 31), owner_id=owner, knowledge_base_id=kb,
                                            filters=RetrievalFilters(document_ids=[])) == []
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id.in_([owner, other])))
            await db.commit()
        await engine.dispose()
