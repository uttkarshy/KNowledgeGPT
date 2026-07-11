"""
Provider factory.

This is the ONE place in the entire codebase where `settings.LLM_PROVIDER`
is inspected. Every other module (RAG engine, upload/embedding worker, chat
router) calls `get_llm_provider()` and receives an `LLMProvider` — it never
knows or cares whether that's OpenAI, vLLM, Ollama, NIM, llama.cpp, or HF.

To add a real (non-stub) local provider:
  1. Implement it in this package (e.g. local_vllm_provider.py) against
     LLMProvider.
  2. Import it below and add one line to PROVIDER_REGISTRY.
  3. Set LLM_PROVIDER=local_vllm (and LOCAL_LLM_BASE_URL) in the environment.
No changes anywhere else.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from app.core.config import LLMProviderName, Settings, get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.openai_provider import OpenAIProvider

# Providers below are architectural placeholders: the interface, registry,
# and config wiring are real and final; the implementations raise until a
# concrete backend is filled in. This is intentional — swapping in a real
# vLLM/Ollama/NIM/llama.cpp/HF backend later requires editing only the
# corresponding provider file, never this factory's shape.
from app.services.llm.future_providers import (
    HuggingFaceProvider,
    LlamaCppProvider,
    LocalOllamaProvider,
    LocalVLLMProvider,
    NvidiaNIMProvider,
)

PROVIDER_REGISTRY: dict[LLMProviderName, Callable[[Settings], LLMProvider]] = {
    LLMProviderName.OPENAI: OpenAIProvider,
    LLMProviderName.LOCAL_VLLM: LocalVLLMProvider,
    LLMProviderName.LOCAL_OLLAMA: LocalOllamaProvider,
    LLMProviderName.NVIDIA_NIM: NvidiaNIMProvider,
    LLMProviderName.LLAMA_CPP: LlamaCppProvider,
    LLMProviderName.HUGGINGFACE: HuggingFaceProvider,
}


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Return the singleton LLMProvider instance selected by configuration.

    FastAPI dependency usage:

        @router.post("/chat")
        async def chat(provider: LLMProvider = Depends(get_llm_provider)):
            ...
    """
    settings = get_settings()
    provider_cls = PROVIDER_REGISTRY.get(settings.LLM_PROVIDER)
    if provider_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
            f"Valid options: {[p.value for p in PROVIDER_REGISTRY]}"
        )
    return provider_cls(settings)
