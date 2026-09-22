"""
OpenAIProvider

Implements LLMProvider on top of OpenAI's **Responses API**
(client.responses.create / client.responses.stream), NOT the legacy
Chat Completions API (client.chat.completions.create).

Why Responses API:
  - Single unified endpoint for text, tools, and future multimodal/agentic use
  - Native streaming event model (response.output_text.delta, response.completed, ...)
  - Server-side state/tool orchestration ready for future agentic RAG features
  - This is OpenAI's forward-looking API surface; Chat Completions is in
    maintenance mode.

This file is the ONLY place that talks to the `openai` SDK. Every other
service in the app (RAG engine, chat router, embedding worker) depends only
on app.services.llm.base.LLMProvider and app.schemas.llm.*.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.core.config import Settings
from app.schemas.llm import (
    ChatMessage,
    EmbeddingRequest,
    EmbeddingResult,
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMStreamChunk,
    LLMUsage,
    MessageRole,
)
from app.services.llm.base import (
    LLMInvalidRequestError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMTransientError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


def _to_responses_input(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Translate provider-agnostic ChatMessage list into the Responses API
    `input` format: a list of role/content items.

    System messages are passed as role="system" items; the Responses API
    accepts system/developer instructions this way (as opposed to the
    separate top-level `instructions` field, which we reserve for a single
    static system prompt if callers prefer that path).
    """
    role_map = {
        MessageRole.SYSTEM: "system",
        MessageRole.USER: "user",
        MessageRole.ASSISTANT: "assistant",
    }
    return [
        {
            "role": role_map[m.role],
            "content": [{"type": "input_text", "text": m.content}]
            if role_map[m.role] != "assistant"
            else [{"type": "output_text", "text": m.content}],
        }
        for m in messages
    ]


def _extract_output_text(response: Any) -> str:
    """The Responses API exposes a convenience `output_text` aggregate on the
    SDK response object. We still guard against it being absent (e.g. tool-
    call-only responses) and fall back to walking `output`."""
    text = getattr(response, "output_text", None)
    if text:
        return text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) == "output_text":
                chunks.append(content.text)
    return "".join(chunks)


class OpenAIProvider(LLMProvider):
    """LLMProvider implementation backed by OpenAI's Responses API."""

    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or None,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    # ------------------------------------------------------------------
    # Chat completion (non-streaming)
    # ------------------------------------------------------------------
    async def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        model = request.model or self._settings.LLM_CHAT_MODEL
        try:
            response = await self._client.responses.create(
                model=model,
                input=_to_responses_input(request.messages),
                temperature=request.temperature
                if request.temperature is not None
                else self._settings.LLM_TEMPERATURE,
                max_output_tokens=request.max_output_tokens
                or self._settings.LLM_MAX_OUTPUT_TOKENS,
                **request.extra,
            )
        except AuthenticationError as e:
            raise LLMProviderError(f"OpenAI authentication failed: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except BadRequestError as e:
            raise LLMInvalidRequestError(f"OpenAI rejected request: {e}") from e
        except APIConnectionError as e:
            raise LLMTransientError("OpenAI connection failed. Please retry later.") from e

        usage = LLMUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
            total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
        ) if getattr(response, "usage", None) else LLMUsage()

        return LLMCompletionResult(
            content=_extract_output_text(response),
            model=model,
            usage=usage,
            finish_reason=getattr(response, "status", "completed") or "completed",
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
        )

    # ------------------------------------------------------------------
    # Chat completion (streaming)
    # ------------------------------------------------------------------
    async def stream(
        self, request: LLMCompletionRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        model = request.model or self._settings.LLM_CHAT_MODEL
        try:
            async with self._client.responses.stream(
                model=model,
                input=_to_responses_input(request.messages),
                temperature=request.temperature
                if request.temperature is not None
                else self._settings.LLM_TEMPERATURE,
                max_output_tokens=request.max_output_tokens
                or self._settings.LLM_MAX_OUTPUT_TOKENS,
                **request.extra,
            ) as stream:
                async for event in stream:
                    event_type = getattr(event, "type", "")

                    if event_type == "response.output_text.delta":
                        yield LLMStreamChunk(delta=event.delta)

                    elif event_type == "response.completed":
                        final = event.response
                        usage = None
                        if getattr(final, "usage", None):
                            usage = LLMUsage(
                                input_tokens=final.usage.input_tokens or 0,
                                output_tokens=final.usage.output_tokens or 0,
                                total_tokens=final.usage.total_tokens or 0,
                            )
                        yield LLMStreamChunk(
                            done=True,
                            finish_reason="completed",
                            usage=usage,
                        )

                    elif event_type == "response.error":
                        raise LLMProviderError(
                            f"OpenAI streaming error: {getattr(event, 'error', event)}"
                        )
        except AuthenticationError as e:
            raise LLMProviderError(f"OpenAI authentication failed: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except BadRequestError as e:
            raise LLMInvalidRequestError(f"OpenAI rejected request: {e}") from e
        except APIConnectionError as e:
            raise LLMTransientError("OpenAI connection failed. Please retry later.") from e

    # ------------------------------------------------------------------
    # Embeddings (separate endpoint — Responses API does not do embeddings)
    # ------------------------------------------------------------------
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        model = request.model or self._settings.LLM_EMBEDDING_MODEL
        try:
            response = await self._client.embeddings.create(
                model=model,
                input=request.texts,
                dimensions=self._settings.LLM_EMBEDDING_DIMENSIONS,
            )
        except AuthenticationError as e:
            raise LLMProviderError(f"OpenAI authentication failed: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except BadRequestError as e:
            raise LLMInvalidRequestError(f"OpenAI rejected request: {e}") from e
        except APIConnectionError as e:
            raise LLMProviderError(f"OpenAI connection error: {e}") from e

        vectors = [item.embedding for item in response.data]
        usage = LLMUsage(
            input_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
            total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
        )

        return EmbeddingResult(
            embeddings=vectors,
            model=model,
            dimensions=len(vectors[0]) if vectors else self._settings.LLM_EMBEDDING_DIMENSIONS,
            usage=usage,
        )

    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        try:
            await self._client.models.retrieve(self._settings.LLM_CHAT_MODEL)
            return True
        except Exception as e:  # noqa: BLE001 — health check must never raise
            logger.warning("OpenAI health check failed category=%s", type(e).__name__)
            return False

    async def aclose(self) -> None:
        await self._client.close()
