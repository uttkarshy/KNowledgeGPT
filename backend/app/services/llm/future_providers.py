"""
Placeholder implementations for future local/self-hosted inference backends.

Each class already satisfies the LLMProvider interface (so the factory,
type hints, and dependency injection all work today) but raises
NotImplementedError until a concrete backend is wired up. This lets the
architecture, config, and registry ship now, with each backend becoming a
same-shape, isolated follow-up:

  - LocalVLLMProvider   -> talk to a vLLM OpenAI-compatible server
  - LocalOllamaProvider -> talk to a local Ollama daemon
  - NvidiaNIMProvider   -> talk to an NVIDIA NIM microservice endpoint
  - LlamaCppProvider    -> talk to llama.cpp's server (llama-server) or bindings
  - HuggingFaceProvider -> local `transformers` pipeline or TGI endpoint

All of them are expected to be OpenAI-wire-compatible or close to it (vLLM,
NIM, and llama-server all expose OpenAI-compatible HTTP APIs), so in
practice most of these will end up thin subclasses that just point
AsyncOpenAI's base_url at a local endpoint — see LOCAL_LLM_BASE_URL in
config.py.
"""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import Settings
from app.schemas.llm import (
    EmbeddingRequest,
    EmbeddingResult,
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMStreamChunk,
)
from app.services.llm.base import LLMProvider


class _UnimplementedLocalProvider(LLMProvider):
    """Shared scaffold for not-yet-implemented local backends."""

    name = "unimplemented"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        raise NotImplementedError(
            f"{self.name} provider is not yet implemented. "
            f"Implement it in app/services/llm/future_providers.py."
        )

    async def stream(
        self, request: LLMCompletionRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        raise NotImplementedError(f"{self.name} provider streaming not yet implemented.")
        yield  # pragma: no cover

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        raise NotImplementedError(f"{self.name} provider embeddings not yet implemented.")

    async def health_check(self) -> bool:
        return False


class LocalVLLMProvider(_UnimplementedLocalProvider):
    name = "local_vllm"


class LocalOllamaProvider(_UnimplementedLocalProvider):
    name = "local_ollama"


class NvidiaNIMProvider(_UnimplementedLocalProvider):
    name = "nvidia_nim"


class LlamaCppProvider(_UnimplementedLocalProvider):
    name = "llama_cpp"


class HuggingFaceProvider(_UnimplementedLocalProvider):
    name = "huggingface"
