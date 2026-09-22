"""
GeminiProvider

Implements LLMProvider on top of Google's **google-genai** SDK (the
current, unified Gen AI SDK — package `google-genai`, imported as
`google.genai`), NOT the deprecated `google-generativeai` package, which
Google has put into maintenance mode in favor of this one.

Key differences from OpenAIProvider that this file has to bridge:
  - Gemini has no "system" role inside the conversation turns. A system
    prompt is instead passed as a separate `system_instruction` field on
    the request config. Multiple SYSTEM messages (rare in this codebase,
    but the schema allows it) are joined into one string.
  - Gemini's conversation roles are "user" and "model", not "user" and
    "assistant". ASSISTANT messages are mapped to role="model".
  - There is no separate embeddings endpoint/client — embeddings go
    through the same `models` surface as generation
    (`client.aio.models.embed_content`), and its response carries no
    token-usage metadata for the standard Developer API (only an
    optional billable-character count reserved for the Gemini Enterprise
    Agent Platform), so LLMUsage() is returned as zeros with a comment
    rather than fabricated numbers.
  - The SDK's error hierarchy is coarser than OpenAI's: everything is
    either ClientError (4xx) or ServerError (5xx), carrying the real HTTP
    status on `.code`, rather than distinct AuthenticationError /
    RateLimitError / BadRequestError classes. This file recovers the same
    granularity our callers expect by branching on `.code`.
  - `client.aio.models.generate_content_stream(...)` is itself a
    coroutine that resolves to an async iterator — it must be awaited
    once to get the stream, then iterated with `async for`, unlike a
    plain async-generator call.

This file is the ONLY place that talks to the `google-genai` SDK. Every
other service in the app (RAG engine, chat router, embedding worker)
depends only on app.services.llm.base.LLMProvider and app.schemas.llm.*.

Expected configuration (see app/core/config.py):
  - settings.GOOGLE_GEMINI_API_KEY   (required)
  - settings.GOOGLE_GEMINI_BASE_URL  (optional — custom endpoint/proxy)
  - settings.LLM_CHAT_MODEL          (e.g. "gemini-2.5-flash")
  - settings.LLM_EMBEDDING_MODEL     (e.g. "gemini-embedding-001")
  - settings.LLM_EMBEDDING_DIMENSIONS
  - settings.LLM_TEMPERATURE
  - settings.LLM_MAX_OUTPUT_TOKENS
  - settings.LLM_TIMEOUT_SECONDS
These are the same provider-agnostic LLM_* fields OpenAIProvider reads —
model names and tunables are pure config, never hardcoded here. The two
Gemini-specific fields are named GOOGLE_GEMINI_* (not GEMINI_*) to match
this project's actual config.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import AsyncIterator

import httpx
from google import genai
from google.genai import types
from google.genai.errors import ClientError

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


def _to_gemini_contents(messages: list[ChatMessage]) -> tuple[str | None, list[types.Content]]:
    """Splits a provider-agnostic message list into (system_instruction,
    contents) — Gemini has no "system" turn in the conversation itself.

    ASSISTANT maps to role="model" (Gemini's name for that turn, not
    "assistant"); USER maps to role="user" unchanged.
    """
    system_parts: list[str] = []
    contents: list[types.Content] = []

    for m in messages:
        if m.role == MessageRole.SYSTEM:
            system_parts.append(m.content)
        elif m.role == MessageRole.USER:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m.content)]))
        elif m.role == MessageRole.ASSISTANT:
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=m.content)]))

    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


def _extract_text(response: types.GenerateContentResponse) -> str:
    """Gemini's response exposes a convenience `.text` aggregate (like
    OpenAI's `output_text`); fall back to walking candidates/parts for
    responses where it's absent (e.g. safety-blocked or tool-call-only)."""
    text = getattr(response, "text", None)
    if text:
        return text

    chunks: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(part_text)
    return "".join(chunks)


def _extract_usage(usage_metadata: types.GenerateContentResponseUsageMetadata | None) -> LLMUsage:
    if usage_metadata is None:
        return LLMUsage()
    return LLMUsage(
        input_tokens=usage_metadata.prompt_token_count or 0,
        output_tokens=usage_metadata.candidates_token_count or 0,
        total_tokens=usage_metadata.total_token_count or 0,
    )


def _extract_finish_reason(response: types.GenerateContentResponse) -> str:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return "completed"
    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason is None:
        return "completed"
    # FinishReason is a str-backed enum (e.g. FinishReason.STOP); `.value`
    # gives the clean "STOP" rather than str()'s "FinishReason.STOP".
    return getattr(finish_reason, "value", None) or str(finish_reason)


def _retry_after(e: Exception) -> float | None:
    delays = []
    value = getattr(getattr(e, 'response', None), 'headers', {}).get('Retry-After')
    if value:
        try:
            delays.append(float(value))
        except (ValueError, TypeError):
            try:
                delays.append((parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    payload = getattr(e, 'details', {}) or {}
    if isinstance(payload, dict):
        error = payload.get('error',payload)
        for detail in error.get('details', []) if isinstance(error, dict) else []:
            if isinstance(detail, dict) and 'retryDelay' in detail:
                try:
                    delays.append(float(str(detail['retryDelay']).removesuffix('s')))
                except (ValueError, TypeError):
                    pass
    return max((v for v in delays if math.isfinite(v) and v>=0), default=None)


def _translate_error(e: Exception) -> LLMProviderError:
    """Maps google-genai SDK exceptions to our provider-agnostic exception
    types. The SDK's error taxonomy is coarser than OpenAI's (ClientError
    for all 4xx, ServerError for all 5xx, rather than distinct
    AuthenticationError/RateLimitError/BadRequestError classes), so the
    real HTTP status carried on `.code` is inspected to recover the same
    granularity our callers expect from any LLMProvider implementation.
    """
    code = getattr(e, "code", None)
    if code in (500, 502, 503, 504):
        return LLMTransientError("Gemini is temporarily unavailable. Please retry later.")
    if isinstance(e, ClientError):
        if code == 429 or getattr(e,"status",None) == "RESOURCE_EXHAUSTED":
            return LLMRateLimitError("Gemini quota reached. Please try again later.", retry_after=_retry_after(e))
        if code in (401, 403):
            return LLMProviderError("Gemini authentication failed. Contact support.")
        if code in (400, 404, 422):
            return LLMInvalidRequestError("Gemini rejected the request or model configuration.")
    if isinstance(e, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return LLMTimeoutError("Gemini request timed out. Please retry.")
    if isinstance(e, (httpx.ConnectError, httpx.NetworkError)):
        return LLMTransientError("Gemini network connection failed. Please retry later.")
    return LLMProviderError("Gemini is unavailable. Please retry later.")


class GeminiProvider(LLMProvider):
    """LLMProvider implementation backed by Google's Gemini API via the
    google-genai SDK."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.GOOGLE_GEMINI_API_KEY:
            raise LLMProviderError("GOOGLE_GEMINI_API_KEY is not configured")
        self._settings = settings
        self._client = genai.Client(
            api_key=settings.GOOGLE_GEMINI_API_KEY,
            http_options=types.HttpOptions(
                base_url=settings.GOOGLE_GEMINI_BASE_URL or None,
                # HttpOptions.timeout is in MILLISECONDS, unlike
                # OpenAIProvider's timeout (seconds) — converted here so
                # settings.LLM_TIMEOUT_SECONDS stays provider-agnostic and
                # this is the only place the unit conversion happens.
                timeout=int(settings.LLM_TIMEOUT_SECONDS * 1000),
                retry_options=types.HttpRetryOptions(attempts=settings.LLM_MAX_RETRIES + 1),
            ),
        )

    # ------------------------------------------------------------------
    # Chat completion (non-streaming)
    # ------------------------------------------------------------------
    async def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        model = request.model or self._settings.LLM_CHAT_MODEL
        system_instruction, contents = _to_gemini_contents(request.messages)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=request.temperature if request.temperature is not None else self._settings.LLM_TEMPERATURE,
            max_output_tokens=min(request.max_output_tokens or self._settings.LLM_MAX_OUTPUT_TOKENS, self._settings.LLM_MAX_OUTPUT_TOKENS),
            **request.extra,
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            raise _translate_error(e) from e

        return LLMCompletionResult(
            content=_extract_text(response),
            model=model,
            usage=_extract_usage(response.usage_metadata),
            finish_reason=_extract_finish_reason(response),
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
        )

    # ------------------------------------------------------------------
    # Chat completion (streaming)
    # ------------------------------------------------------------------
    async def stream(
        self, request: LLMCompletionRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        model = request.model or self._settings.LLM_CHAT_MODEL
        system_instruction, contents = _to_gemini_contents(request.messages)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=request.temperature if request.temperature is not None else self._settings.LLM_TEMPERATURE,
            max_output_tokens=min(request.max_output_tokens or self._settings.LLM_MAX_OUTPUT_TOKENS, self._settings.LLM_MAX_OUTPUT_TOKENS),
            **request.extra,
        )

        try:
            # generate_content_stream is a coroutine that RESOLVES to an
            # async iterator (unlike a plain async-generator function) —
            # it must be awaited once here to get the stream, then
            # iterated separately below.
            response_stream = await self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )

            final_usage: LLMUsage | None = None
            async for chunk in response_stream:
                delta = _extract_text(chunk)
                if delta:
                    yield LLMStreamChunk(delta=delta)
                if getattr(chunk, "usage_metadata", None):
                    final_usage = _extract_usage(chunk.usage_metadata)

            yield LLMStreamChunk(
                done=True,
                finish_reason="completed",
                usage=final_usage,
            )
        except Exception as e:
            raise _translate_error(e) from e

    # ------------------------------------------------------------------
    # Embeddings (same `models` surface — Gemini has no separate embeddings client)
    # ------------------------------------------------------------------
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        model = request.model or self._settings.LLM_EMBEDDING_MODEL
        if len(request.texts) > self._settings.EMBEDDING_BATCH_SIZE:
            raise LLMInvalidRequestError("Embedding batch exceeds configured limit")
        if any(not text.strip() or len(text.encode("utf-8")) > self._settings.EMBEDDING_MAX_INPUT_BYTES for text in request.texts):
            raise LLMInvalidRequestError("Embedding text is empty or exceeds the safe input budget")
        try:
            response = await self._client.aio.models.embed_content(
                model=model,
                contents=request.texts,
                # Without this, gemini-embedding-001 returns 3072-dimensional
                # vectors by default — which will silently fail (or corrupt)
                # inserts into a pgvector column sized for
                # settings.LLM_EMBEDDING_DIMENSIONS (e.g. 1536) if left
                # unset. Gemini's embedding models support Matryoshka
                # truncation via this parameter, so requesting the
                # configured dimension directly is both correct and
                # (slightly) cheaper to store than truncating client-side.
                config=types.EmbedContentConfig(
                    output_dimensionality=self._settings.LLM_EMBEDDING_DIMENSIONS,
                    task_type=request.task_type,
                    # Durable worker retries own the embedding budget.
                    http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
                ),
            )
        except Exception as e:
            raise _translate_error(e) from e

        vectors = [list(embedding.values or []) for embedding in (response.embeddings or [])]
        dim = self._settings.LLM_EMBEDDING_DIMENSIONS
        if len(vectors) != len(request.texts) or any(len(v) != dim for v in vectors):
            raise LLMProviderError("Gemini embedding count or dimension does not match the schema")
        normalized = []
        for vector in vectors:
            norm = math.sqrt(sum(value * value for value in vector))
            if not math.isfinite(norm) or norm == 0:
                raise LLMProviderError("Gemini returned an invalid embedding vector")
            normalized.append([value / norm for value in vector])
        vectors = normalized

        return EmbeddingResult(
            embeddings=vectors,
            model=model,
            dimensions=len(vectors[0]) if vectors else self._settings.LLM_EMBEDDING_DIMENSIONS,
            # The standard Gemini Developer API does not return token usage
            # for embeddings (EmbedContentResponse.metadata only carries a
            # billable-character count, and only on the separate Gemini
            # Enterprise Agent Platform) — zeros here are honest silence,
            # not a fabricated count.
            usage=LLMUsage(),
        )

    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        try:
            await self._client.aio.models.get(model=self._settings.LLM_CHAT_MODEL)
            await self._client.aio.models.get(model=self._settings.LLM_EMBEDDING_MODEL)
            return True
        except Exception as e:  # noqa: BLE001 — health check must never raise
            logger.warning("Gemini health check failed category=%s", type(e).__name__)
            return False
        
    async def aclose(self) -> None:
        await self._client.aio.aclose()
        self._client.close()
