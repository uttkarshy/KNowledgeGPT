import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from google.genai import types
from google.genai.errors import ClientError

from app.core.config import Settings
from app.schemas.llm import ChatMessage, EmbeddingRequest, LLMCompletionRequest, MessageRole
from app.services.llm.base import LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.services.llm.factory import build_llm_provider
from app.services.llm.gemini_provider import GeminiProvider, _translate_error


@pytest.fixture
def provider():
    settings = Settings(_env_file=None, GOOGLE_GEMINI_API_KEY="unit-test-key")
    with patch("app.services.llm.gemini_provider.genai.Client") as factory:
        client = factory.return_value
        client.aio.aclose = AsyncMock()
        p = GeminiProvider(settings)
        yield p, client, factory


def test_factory_and_sdk_configuration(provider):
    p, client, factory = provider
    assert factory.call_args.kwargs["api_key"] == "unit-test-key"
    options = factory.call_args.kwargs["http_options"]
    assert options.timeout == 60000
    assert options.retry_options.attempts == 3
    assert isinstance(build_llm_provider(Settings(GOOGLE_GEMINI_API_KEY="unit-test-key")), GeminiProvider)
    with pytest.raises(LLMProviderError):
        GeminiProvider(Settings(_env_file=None, GOOGLE_GEMINI_API_KEY=None))


@pytest.mark.asyncio
async def test_embed_requests_exact_dimension_and_normalizes(provider):
    p, client, _ = provider
    client.aio.models.embed_content = AsyncMock(return_value=types.EmbedContentResponse(
        embeddings=[types.ContentEmbedding(values=[2.0] * 1536)]))
    result = await p.embed(EmbeddingRequest(texts=["school library"], task_type="RETRIEVAL_QUERY"))
    call = client.aio.models.embed_content.call_args.kwargs
    assert call["model"] == "gemini-embedding-001"
    assert call["config"].output_dimensionality == 1536
    assert call["config"].task_type == "RETRIEVAL_QUERY"
    assert result.dimensions == 1536
    assert math.isclose(sum(x*x for x in result.embeddings[0]), 1.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("vectors", [[], [[1.0]*3072], [[0.0]*1536], [[float("nan")]*1536]])
async def test_invalid_embedding_rejected(provider, vectors):
    p, client, _ = provider
    client.aio.models.embed_content = AsyncMock(return_value=SimpleNamespace(
        embeddings=[SimpleNamespace(values=v) for v in vectors]))
    with pytest.raises(LLMProviderError):
        await p.embed(EmbeddingRequest(texts=["text"]))


@pytest.mark.asyncio
async def test_chat_and_stream_roles_usage_and_cleanup(provider):
    p, client, _ = provider
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="Grounded answer [1]")]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=20, candidates_token_count=5, total_token_count=25))
    client.aio.models.generate_content = AsyncMock(return_value=response)
    request = LLMCompletionRequest(messages=[ChatMessage(role=MessageRole.SYSTEM, content="Use sources"),
        ChatMessage(role=MessageRole.USER, content="Question"), ChatMessage(role=MessageRole.ASSISTANT, content="Earlier")])
    result = await p.complete(request)
    assert result.content == "Grounded answer [1]"
    call = client.aio.models.generate_content.call_args.kwargs
    assert call["config"].system_instruction == "Use sources"
    assert [c.role for c in call["contents"]] == ["user", "model"]
    async def chunks():
        yield response
    client.aio.models.generate_content_stream = AsyncMock(return_value=chunks())
    events = [e async for e in p.stream(request)]
    assert events[-1].done and events[-1].usage.total_tokens == 25
    client.aio.models.get = AsyncMock()
    assert await p.health_check()
    assert client.aio.models.get.await_count == 2
    await p.aclose()
    client.aio.aclose.assert_awaited_once()


def test_errors_are_classified_without_leaking_response_body():
    err = _translate_error(ClientError(429, {"error": {"message": "private-key-and-document"}}))
    assert isinstance(err, LLMRateLimitError)
    assert "private-key" not in str(err)
    assert isinstance(_translate_error(httpx.ReadTimeout("secret")), LLMTimeoutError)
