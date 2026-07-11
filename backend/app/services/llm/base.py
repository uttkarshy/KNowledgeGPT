"""
LLMProvider — the single interface every model backend implements.

    LLMProvider
      |
      +-- OpenAIProvider          (implemented now, uses Responses API)
      +-- LocalVLLMProvider       (future)
      +-- OllamaProvider          (future)
      +-- NvidiaNIMProvider       (future)
      +-- LlamaCppProvider        (future)
      +-- HuggingFaceProvider     (future)

Adding a new provider means:
  1. Create a new class in this package implementing LLMProvider.
  2. Register it in factory.py's PROVIDER_REGISTRY.
  3. Set LLM_PROVIDER in the environment.
No other file in the application changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.schemas.llm import (
    EmbeddingRequest,
    EmbeddingResult,
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMStreamChunk,
)


class LLMProviderError(Exception):
    """Base exception for all provider errors. Providers must wrap SDK-specific
    exceptions in this (or a subclass) so callers never need to catch
    provider-specific exception types."""


class LLMRateLimitError(LLMProviderError):
    pass


class LLMTimeoutError(LLMProviderError):
    pass


class LLMInvalidRequestError(LLMProviderError):
    pass


class LLMProvider(ABC):
    """Abstract base class for all LLM backends.

    Implementations must be fully async and must never leak SDK-specific
    exception types or response objects — everything in and out is one of
    the schemas in app.schemas.llm.
    """

    name: str

    @abstractmethod
    async def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        """Non-streaming chat completion."""
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self, request: LLMCompletionRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        """Streaming chat completion. Yields normalized LLMStreamChunk objects."""
        raise NotImplementedError
        yield  # pragma: no cover — makes this an async generator for type checkers

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Generate embeddings for a batch of texts."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Cheap liveness check used by /health and admin dashboard."""
        raise NotImplementedError
