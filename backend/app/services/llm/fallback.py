from __future__ import annotations

from typing import AsyncIterator

from app.core.config import Settings
from app.schemas.llm import EmbeddingRequest, EmbeddingResult, LLMCompletionRequest, LLMCompletionResult, LLMStreamChunk
from app.services.llm.base import LLMProvider, LLMRateLimitError, LLMTimeoutError, LLMTransientError


class PrimaryWithFallbackProvider(LLMProvider):
    name = "primary_with_fallback"

    def __init__(self, primary: LLMProvider, fallback: LLMProvider, settings: Settings) -> None:
        self._primary, self._fallback, self._settings = primary, fallback, settings

    async def stream(self, request: LLMCompletionRequest) -> AsyncIterator[LLMStreamChunk]:
        try:
            async for chunk in self._primary.stream(request):
                yield chunk
            return
        except (LLMTransientError, LLMRateLimitError, LLMTimeoutError):
            pass
        fallback_request = request.model_copy(update={"model": self._settings.LLM_FALLBACK_CHAT_MODEL})
        async for chunk in self._fallback.stream(fallback_request):
            yield chunk

    async def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        try:
            return await self._primary.complete(request)
        except (LLMTransientError, LLMRateLimitError, LLMTimeoutError):
            fallback_request = request.model_copy(update={"model": self._settings.LLM_FALLBACK_CHAT_MODEL})
            return await self._fallback.complete(fallback_request)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return await self._primary.embed(request)

    async def health_check(self) -> bool:
        return await self._primary.health_check()

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._fallback.aclose()
