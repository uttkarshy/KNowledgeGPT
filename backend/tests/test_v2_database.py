"""Real migrated PostgreSQL checkpoints, isolation and stable citation numbering."""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.chat import ChatCitation, ChatMessage, ChatSession
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType, MessageRole
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.llm import EmbeddingResult
from app.services.chunking.semantic_chunker import Chunk
from app.services.embedding import pipeline
from app.services.llm.base import LLMRateLimitError
from app.services.rag.exhaustive import calculate, evidence
from app.services.rag.query_router import route

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL/pgvector")


async def test_real_batch_resume_unique_chunks_counters_isolation_and_citation_order(tmp_path, monkeypatch):
    settings = Settings(EMBEDDING_BATCH_SIZE=2)
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, other, kb, doc_id = (uuid.uuid4() for _ in range(4))
    path = tmp_path / "synthetic.txt"
    path.write_text("Synthetic financial regression fixture, no private data.")
    texts = [
        f"30 Jul 2026 | Synthetic {i} | Debit {amount}"
        for i, amount in enumerate(["14.00", "1540.00", "35.00", "255.00"])
    ]
    monkeypatch.setattr(pipeline, "chunk_document", lambda _: [Chunk(t, 1, None, 20) for t in texts])
    result = EmbeddingResult(embeddings=[[1.0] + [0.0] * 1535] * 2, dimensions=1536, model=settings.LLM_EMBEDDING_MODEL)
    provider = SimpleNamespace(embed=AsyncMock(side_effect=[result, LLMRateLimitError("synthetic quota")]))
    try:
        async with sessions() as db:
            db.add_all([User(id=u, email=f"v2-{u}@example.com") for u in (owner, other)])
            await db.flush()
            db.add(KnowledgeBase(id=kb, owner_id=owner, name="Synthetic"))
            await db.flush()
            db.add(
                Document(
                    id=doc_id,
                    owner_id=owner,
                    knowledge_base_id=kb,
                    name="synthetic.txt",
                    file_type=FileType.TXT,
                    status=DocumentStatus.EXTRACTING,
                    checksum="a" * 64,
                )
            )
            await db.commit()
            with pytest.raises(LLMRateLimitError):
                await pipeline.process_document_embeddings(
                    db, settings=settings, provider=provider, document_id=doc_id, local_file_path=str(path)
                )
        # New session models a worker restart, not an in-memory retry.
        async with sessions() as db:
            saved = list((await db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))).all())
            assert sorted(c.chunk_index for c in saved) == [0, 1]
            assert await evidence(db, owner_id=owner, kb_id=kb) == []  # incomplete data cannot leak
            provider.embed = AsyncMock(return_value=result)
            assert (
                await pipeline.process_document_embeddings(
                    db, settings=settings, provider=provider, document_id=doc_id, local_file_path=str(path)
                )
                == 4
            )
            await db.commit()
            assert provider.embed.await_count == 1
            assert provider.embed.call_args.args[0].texts == texts[2:]
            assert (
                await pipeline.process_document_embeddings(
                    db, settings=settings, provider=provider, document_id=doc_id, local_file_path=str(path)
                )
                == 4
            )
            assert provider.embed.await_count == 1
            counters = await db.get(KnowledgeBase, kb)
            assert (counters.document_count, counters.total_chunk_count) == (1, 4)
            rows = await evidence(db, owner_id=owner, kb_id=kb)
            assert len(rows) == 4
            assert await evidence(db, owner_id=other, kb_id=kb) == []
            assert await evidence(db, owner_id=owner, kb_id=uuid.uuid4()) == []
            answer, sources = calculate(
                rows, route("3 largest expenses in July 2026"), "3 largest expenses in July 2026"
            )
            assert "1,540.00" in answer and "255.00" in answer and "35.00" in answer and "14.00" not in answer
            chat = ChatSession(owner_id=owner, knowledge_base_id=kb)
            db.add(chat)
            await db.flush()
            message = ChatMessage(session_id=chat.id, role=MessageRole.ASSISTANT, content="Synthetic [1] [2]")
            db.add(message)
            await db.flush()
            message_id = message.id
            for index in (2, 1):
                source = sources[index - 1]
                db.add(
                    ChatCitation(
                        message_id=message.id,
                        document_id=doc_id,
                        chunk_id=source.chunk_id,
                        document_name="synthetic.txt",
                        source_index=index,
                        excerpt=source.content,
                        similarity_score=1,
                    )
                )
            await db.commit()
        async with sessions() as db:
            message = await db.scalar(
                select(ChatMessage).where(ChatMessage.id == message_id).options(selectinload(ChatMessage.citations))
            )
            assert [c.source_index for c in message.citations] == [1, 2]
            db.add(
                DocumentChunk(
                    document_id=doc_id,
                    owner_id=owner,
                    knowledge_base_id=kb,
                    chunk_index=0,
                    content="duplicate",
                    embedding=[1.0] + [0.0] * 1535,
                    embedding_model=settings.LLM_EMBEDDING_MODEL,
                    checksum="b" * 64,
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id.in_([owner, other])))
            await db.commit()
        await engine.dispose()
