"""
Provider-agnostic data contracts for the LLM abstraction layer.

Every provider (OpenAI today; vLLM/Ollama/NIM/llama.cpp/HF tomorrow) speaks
ONLY in these types. RAG engine, chat endpoints, and Celery workers never
import a provider-specific type.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class Citation(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    similarity_score: float
    excerpt: str


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMCompletionRequest(BaseModel):
    """Provider-agnostic request. Providers translate this into their own wire format."""

    messages: list[ChatMessage]
    model: Optional[str] = None          # falls back to settings.LLM_CHAT_MODEL
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    stream: bool = False
    # Free-form provider-specific extras (e.g. reasoning effort, tool defs).
    # Kept generic on purpose so new providers can accept new knobs without
    # changing this schema.
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMCompletionResult(BaseModel):
    """Final, non-streaming result shape returned by every provider."""

    content: str
    model: str
    usage: LLMUsage
    finish_reason: str
    raw: dict[str, Any] = Field(default_factory=dict)  # provider raw payload for debugging/audit


class LLMStreamChunk(BaseModel):
    """One chunk of a streamed response. Providers normalize their SSE/stream events to this."""

    delta: str = ""
    reasoning_delta: str = ""  # populated only by providers/models that expose a reasoning trace (e.g. gpt-oss via NIM)
    done: bool = False
    finish_reason: Optional[str] = None
    usage: Optional[LLMUsage] = None


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=100)
    model: Optional[str] = None
    task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] = "RETRIEVAL_DOCUMENT"


class EmbeddingResult(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimensions: int
    usage: LLMUsage = Field(default_factory=LLMUsage)
