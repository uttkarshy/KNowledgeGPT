"""
RAG engine — ties together every piece built in prior increments:

    question -> embed (LLMProvider) -> similarity_search (pgvector)
             -> compress_context -> assemble_messages -> provider.stream()
             -> persist ChatMessage + ChatCitation rows -> stream to client

The "never hallucinate" rule is enforced STRUCTURALLY, not just by prompt
wording: if nothing clears the similarity threshold, the LLM is never
called at all — the configured RAG_NO_ANSWER_MESSAGE is returned directly.
This also saves the cost/latency of a doomed API call.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.chat import ChatCitation, ChatSession
from app.models.chat import ChatMessage as ChatMessageModel
from app.models.enums import MessageRole as DBMessageRole
from app.models.usage import ApiUsageLog
from app.schemas.llm import ChatMessage, LLMCompletionRequest, MessageRole
from app.services.llm.base import LLMProvider
from app.services.rag.context_compression import compress_context
from app.services.rag.exact_date import (
    MAX_CONTEXT_TOKENS,
    DateEvidenceLimit,
    augment_date_context,
    context_cost,
    exact_date_evidence,
)
from app.services.rag.exhaustive import calculate, evidence, named_rows, narrow
from app.services.rag.prompt_assembly import assemble_messages
from app.services.rag.query_router import route
from app.services.rag.retrieval import RetrievalFilters, RetrievedChunk, similarity_search

logger = logging.getLogger(__name__)


def _title_from_question(question: str, max_length: int = 72) -> str:
    """Build a short deterministic chat title from the first question."""
    title = " ".join(question.split())
    if len(title) <= max_length:
        return title
    return title[: max_length - 3].rstrip() + "..."


@dataclass
class RAGStreamEvent:
    type: str  # "delta" | "done" | "no_answer" | "error"
    delta: str = ""
    message_id: uuid.UUID | None = None
    citations: list[dict] = field(default_factory=list)
    confidence: float | None = None
    error: str | None = None


def _load_recent_history(messages: list[ChatMessageModel], limit: int = 10) -> list[ChatMessage]:
    """Converts the last `limit` prior messages into the provider-agnostic
    ChatMessage schema for multi-turn context. Citations from prior turns
    aren't replayed into the prompt — only the assistant's actual answer
    text, to keep the prompt from growing unboundedly with source dumps."""
    recent = messages[-limit:]
    return [
        ChatMessage(
            role=MessageRole.USER if m.role == DBMessageRole.USER else MessageRole.ASSISTANT,
            content=m.content,
        )
        for m in recent
        if m.role in (DBMessageRole.USER, DBMessageRole.ASSISTANT)
    ]


async def _fetch_recent_history(db: AsyncSession, *, session_id: uuid.UUID, limit: int = 10) -> list[ChatMessage]:
    """Explicit query rather than relying on session.messages — that
    relationship is not guaranteed to be eagerly loaded on an AsyncSession,
    and lazy-loading would raise (or silently fail) outside a greenlet-safe
    context here."""
    from sqlalchemy import select

    stmt = (
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session_id)
        .order_by(ChatMessageModel.created_at.desc())
        .limit(limit)
    )
    rows = (await db.scalars(stmt)).all()
    return _load_recent_history(list(reversed(rows)), limit=limit)


async def answer_question(
    db: AsyncSession,
    *,
    settings: Settings,
    provider: LLMProvider,
    session: ChatSession,
    question: str,
    filters: RetrievalFilters | None = None,
):
    """Async generator yielding RAGStreamEvent objects. The caller (FastAPI
    route) turns these into SSE frames."""
    start_time = time.perf_counter()

    # Fetch history BEFORE adding this turn's user message, so it isn't
    # included in its own "prior conversation" context.
    history = await _fetch_recent_history(db, session_id=session.id)

    user_message = ChatMessageModel(session_id=session.id, role=DBMessageRole.USER, content=question)
    db.add(user_message)
    await db.flush()

    if session.title == "New Chat":
        session.title = _title_from_question(question)

    direct_answer = None
    special_context = None
    date_context = None
    limitation = None
    try:
        plan = route(question)
        filters = await narrow(db, owner_id=session.owner_id, kb_id=session.knowledge_base_id, filters=filters, filename=plan.filename)
        target = plan.target
        if plan.strategy in ('analytical', 'lexical'):
            special_context = await evidence(db, owner_id=session.owner_id, kb_id=session.knowledge_base_id,
                                             filters=filters, lexical=question if plan.strategy == 'lexical' else None)
            if plan.financial:
                direct_answer, special_context = calculate(special_context, plan, question)
            elif context_cost(special_context) > MAX_CONTEXT_TOKENS:
                raise DateEvidenceLimit('Complete evidence exceeds the safe context limit. Select fewer documents.')
        elif plan.strategy == 'row':
            rows = await evidence(db, owner_id=session.owner_id, kb_id=session.knowledge_base_id, filters=filters)
            direct_answer, special_context = named_rows(rows, plan.names)
        logger.info('retrieval_strategy=%s', plan.strategy)
        if target:
            date_context = await exact_date_evidence(db, target=target, owner_id=session.owner_id,
                                                    knowledge_base_id=session.knowledge_base_id, filters=filters)
            if plan.financial:
                direct_answer, date_context = calculate(date_context, plan, question)
    except DateEvidenceLimit as exc:
        limitation = str(exc)
    if limitation:
        message = ChatMessageModel(session_id=session.id, role=DBMessageRole.ASSISTANT,
                                   content=limitation, confidence_score=0.0)
        db.add(message)
        await db.flush()
        yield RAGStreamEvent(type="no_answer", delta=limitation, message_id=message.id, confidence=0.0)
        return

    if special_context is not None:
        chunks = special_context
    elif direct_answer is not None and date_context is not None:
        chunks = date_context
    else:
        # ---------------- Embed the question ----------------
        try:
            from app.schemas.llm import EmbeddingRequest

            embed_result = await provider.embed(EmbeddingRequest(texts=[question], task_type="RETRIEVAL_QUERY"))
            if embed_result.dimensions != settings.LLM_EMBEDDING_DIMENSIONS or embed_result.model != settings.LLM_EMBEDDING_MODEL or len(embed_result.embeddings) != 1:
                raise ValueError("Embedding contract mismatch")
            query_embedding = embed_result.embeddings[0]
        except Exception as e:
            logger.warning("question_embedding_failed session=%s category=%s", session.id, type(e).__name__)
            yield RAGStreamEvent(type="error", error="Could not process your question. Please retry or contact support.")
            return

        # ---------------- Retrieve ----------------
        chunks: list[RetrievedChunk] = await similarity_search(
            db,
            knowledge_base_id=session.knowledge_base_id,
            owner_id=session.owner_id,
            query_embedding=query_embedding,
            embedding_model=settings.LLM_EMBEDDING_MODEL,
            top_k=settings.RAG_TOP_K,
            min_similarity=settings.RAG_MIN_SIMILARITY,
            filters=filters,
        )

        if date_context is not None:
            chunks = augment_date_context(date_context, chunks) if date_context else []

    if not chunks:
        assistant_message = ChatMessageModel(
            session_id=session.id,
            role=DBMessageRole.ASSISTANT,
            content=settings.RAG_NO_ANSWER_MESSAGE,
            model_used=None,
            confidence_score=0.0,
            latency_ms=int((time.perf_counter() - start_time) * 1000),
        )
        db.add(assistant_message)
        await db.flush()
        yield RAGStreamEvent(
            type="no_answer",
            delta=settings.RAG_NO_ANSWER_MESSAGE,
            message_id=assistant_message.id,
            confidence=0.0,
        )
        return

    context_chunks = chunks if date_context is not None or special_context is not None else compress_context(chunks, max_context_tokens=3000)
    messages = assemble_messages(question=question, chunks=context_chunks, conversation_history=history)

    # ---------------- Stream the completion ----------------
    full_text_parts: list[str] = []
    input_tokens = output_tokens = 0
    if direct_answer is not None:
        full_text_parts.append(direct_answer)
        yield RAGStreamEvent(type='delta', delta=direct_answer)
    else:
        try:
            async for stream_chunk in provider.stream(LLMCompletionRequest(messages=messages, stream=True)):
                if stream_chunk.delta:
                    full_text_parts.append(stream_chunk.delta)
                    yield RAGStreamEvent(type="delta", delta=stream_chunk.delta)
                if stream_chunk.done and stream_chunk.usage:
                    input_tokens = stream_chunk.usage.input_tokens
                    output_tokens = stream_chunk.usage.output_tokens
        except Exception as e:
            logger.warning("chat_provider_failed session=%s category=%s", session.id, type(e).__name__)
            yield RAGStreamEvent(type="error", error="The model is temporarily unavailable. Please retry.")
            return

    full_text = "".join(full_text_parts)
    if not full_text.strip():
        yield RAGStreamEvent(type="error", error="The model returned no answer. Please rephrase your question.")
        return
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    top_confidence = max(c.similarity for c in context_chunks)

    assistant_message = ChatMessageModel(
        session_id=session.id,
        role=DBMessageRole.ASSISTANT,
        content=full_text,
        model_used=None if direct_answer is not None else settings.LLM_CHAT_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        confidence_score=top_confidence,
    )
    db.add(assistant_message)
    await db.flush()

    citation_dicts: list[dict] = []
    for source_index, chunk in enumerate(context_chunks, 1):
        citation = ChatCitation(
            message_id=assistant_message.id,
            source_index=source_index,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            document_name=chunk.document_name,
            page_number=chunk.page_number,
            section=chunk.section,
            similarity_score=chunk.similarity,
            excerpt=chunk.content,
        )
        db.add(citation)
        citation_dicts.append(
            {
                "chunk_id": str(chunk.chunk_id),
                "document_id": str(chunk.document_id),
                "document_name": chunk.document_name,
                "page_number": chunk.page_number,
                "section": chunk.section,
                "similarity_score": round(chunk.similarity, 4),
                "excerpt": chunk.content,
            }
        )
    await db.flush()
    db.add(ApiUsageLog(user_id=session.owner_id, endpoint="rag/deterministic" if direct_answer is not None else "rag/completion", model=None if direct_answer is not None else settings.LLM_CHAT_MODEL,
                       input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms))

    yield RAGStreamEvent(
        type="done",
        message_id=assistant_message.id,
        citations=citation_dicts,
        confidence=top_confidence,
    )
