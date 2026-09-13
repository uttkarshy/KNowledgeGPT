from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import enforce_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    AskQuestionRequest,
    ChatMessagePublic,
    ChatSessionPublic,
    CreateSessionRequest,
)
from app.services import chat_service
from app.services.llm import get_llm_provider
from app.services.llm.base import LLMProvider
from app.services.rag.engine import answer_question
from app.services.rag.retrieval import RetrievalFilters

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionPublic, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await chat_service.create_session(
            db, owner_id=current_user.id, knowledge_base_id=body.knowledge_base_id, title=body.title
        )
    except chat_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/sessions", response_model=list[ChatSessionPublic])
async def list_sessions(
    knowledge_base_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await chat_service.list_sessions(db, owner_id=current_user.id, knowledge_base_id=knowledge_base_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessagePublic])
async def get_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await chat_service.get_messages(db, session_id=session_id, owner_id=current_user.id)
    except chat_service.SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/sessions/{session_id}/ask")
async def ask_question(
    session_id: uuid.UUID,
    body: AskQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_llm_provider),
):
    """Streams a RAG-grounded, cited answer as Server-Sent Events.

    Event shapes sent to the client:
      data: {"type": "delta", "delta": "..."}
      data: {"type": "no_answer", "delta": "...", "message_id": "..."}
      data: {"type": "done", "message_id": "...", "citations": [...], "confidence": 0.83}
      data: {"type": "error", "error": "..."}
    """
    try:
        session = await chat_service.get_owned_session(db, session_id=session_id, owner_id=current_user.id)
    except chat_service.SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    filters = RetrievalFilters(document_ids=body.document_ids, language=body.language)
    await enforce_limit(settings, key=f"chat:{current_user.id}", limit=settings.RATE_LIMIT_CHAT_PER_MINUTE)
    await enforce_limit(settings, key=f"chat_daily:{current_user.id}", limit=settings.RATE_LIMIT_CHAT_PER_DAY, seconds=86400)
    await enforce_limit(settings, key="chat_global", limit=settings.RATE_LIMIT_GLOBAL_CHAT_PER_DAY, seconds=86400)

    async def event_stream():
        try:
            async with asyncio.timeout(settings.LLM_TIMEOUT_SECONDS * 2):
                async for event in answer_question(
                    db, settings=settings, provider=provider, session=session, question=body.question, filters=filters
                ):
                    if event.type in {"done", "no_answer"}:
                        await db.commit()  # terminal success means persisted, even after immediate refresh
                    elif event.type == "error":
                        await db.rollback()
                    payload = {
                        "type": event.type, "delta": event.delta,
                        "message_id": str(event.message_id) if event.message_id else None,
                        "citations": event.citations, "confidence": event.confidence, "error": event.error,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
        except asyncio.CancelledError:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            logging.getLogger(__name__).error("chat_failed session=%s category=%s", session_id, type(exc).__name__)
            yield 'data: {"type":"error","error":"The answer could not be saved or completed. Please retry."}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"})
