"""Real PostgreSQL/pgvector checks. CI enables these after migrating an empty DB."""

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.chat import ChatCitation, ChatMessage, ChatSession
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType, MessageRole
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services import chat_service, document_service, knowledge_base_service
from app.services.auth.service import (
    InvalidOrExpiredTokenError,
    authenticate_user,
    issue_token_pair,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.services.rag.retrieval import similarity_search

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="NOT VERIFIED: requires a migrated PostgreSQL 16/pgvector database"
)


@pytest.mark.asyncio
async def test_real_registration_refresh_enums_persistence_and_tenant_isolation():
    settings = Settings()
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex
    try:
        async with sessions() as db:
            a = await register_user(
                db,
                settings=settings,
                email=f"a-{suffix}@example.com",
                password="StrongPassword!123",
                full_name="Acceptance A",
            )
            b = await register_user(
                db,
                settings=settings,
                email=f"b-{suffix}@example.com",
                password="StrongPassword!123",
                full_name="Acceptance B",
            )
            await db.commit()
            assert (await authenticate_user(db, email=a.email, password="StrongPassword!123")).id == a.id
            pair = await issue_token_pair(db, user=a, settings=settings, user_agent=None, ip_address=None)
            await db.commit()
            fresh = await rotate_refresh_token(
                db, settings=settings, plaintext_refresh_token=pair.refresh_token, user_agent=None, ip_address=None
            )
            await db.commit()
            await revoke_refresh_token(db, plaintext_refresh_token=fresh.refresh_token)
            await db.commit()
            with pytest.raises(InvalidOrExpiredTokenError):
                await rotate_refresh_token(
                    db, settings=settings, plaintext_refresh_token=fresh.refresh_token, user_agent=None, ip_address=None
                )
            await db.rollback()
            a = await db.scalar(select(User).where(User.email == f"a-{suffix}@example.com"))
            b = await db.scalar(select(User).where(User.email == f"b-{suffix}@example.com"))
            kb_a, kb_b = KnowledgeBase(owner_id=a.id, name="A"), KnowledgeBase(owner_id=b.id, name="B")
            db.add_all([kb_a, kb_b])
            await db.flush()
            doc = Document(
                owner_id=b.id,
                knowledge_base_id=kb_b.id,
                name="private.pdf",
                file_type=FileType.PDF,
                status=DocumentStatus.COMPLETED,
                checksum="x" * 64,
            )
            db.add(doc)
            await db.flush()
            chunk = DocumentChunk(
                document_id=doc.id,
                knowledge_base_id=kb_b.id,
                owner_id=b.id,
                chunk_index=0,
                page_number=1,
                content="Private B content",
                embedding=[0.1] * 1536,
                embedding_model=settings.LLM_EMBEDDING_MODEL,
                checksum="y" * 64,
            )
            db.add(chunk)
            chat = ChatSession(owner_id=b.id, knowledge_base_id=kb_b.id, title="Private B chat")
            db.add(chat)
            await db.flush()
            message = ChatMessage(session_id=chat.id, role=MessageRole.ASSISTANT, content="Private B answer")
            db.add(message)
            await db.flush()
            db.add(
                ChatCitation(
                    message_id=message.id,
                    document_id=doc.id,
                    chunk_id=chunk.id,
                    document_name=doc.name,
                    page_number=1,
                    similarity_score=1.0,
                    excerpt=chunk.content,
                )
            )
            await db.commit()
            assert (
                await similarity_search(
                    db,
                    owner_id=a.id,
                    knowledge_base_id=kb_b.id,
                    query_embedding=[0.1] * 1536,
                    embedding_model=settings.LLM_EMBEDDING_MODEL,
                )
                == []
            )
            own = await similarity_search(
                db,
                owner_id=b.id,
                knowledge_base_id=kb_b.id,
                query_embedding=[0.1] * 1536,
                embedding_model=settings.LLM_EMBEDDING_MODEL,
            )
            assert len(own) == 1 and own[0].chunk_id == chunk.id
            with pytest.raises(document_service.DocumentNotFoundError):
                await document_service.get_owned_document(db, document_id=doc.id, owner_id=a.id)
            with pytest.raises(knowledge_base_service.KnowledgeBaseNotFoundError):
                await knowledge_base_service.get_owned_knowledge_base(db, kb_id=kb_b.id, owner_id=a.id)
            with pytest.raises(chat_service.SessionNotFoundError):
                await chat_service.get_messages(db, session_id=chat.id, owner_id=a.id)
            messages = await chat_service.get_messages(db, session_id=chat.id, owner_id=b.id)
            assert messages[0].citations[0].chunk_id == chunk.id
            # Prove a fresh session reads persisted chat/citation state.
            message_id = message.id
            await db.rollback()
        async with sessions() as db:
            saved = await db.scalar(
                select(ChatMessage).where(ChatMessage.id == message_id).options(selectinload(ChatMessage.citations))
            )
            assert saved and saved.citations[0].page_number == 1
    finally:
        await engine.dispose()
