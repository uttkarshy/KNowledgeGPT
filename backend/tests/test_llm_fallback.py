from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.schemas.llm import ChatMessage, LLMCompletionRequest, LLMStreamChunk, MessageRole
from app.services.llm.base import LLMProvider, LLMProviderError, LLMRateLimitError, LLMTransientError
from app.services.llm.fallback import PrimaryWithFallbackProvider


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, events=None, error=None):
        self.events, self.error, self.calls = events or [], error, []

    async def stream(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        for event in self.events:
            yield event

    async def complete(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(content="ok")

    async def embed(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    async def health_check(self):
        return True


def request():
    return LLMCompletionRequest(messages=[ChatMessage(role=MessageRole.USER, content="same grounded context")])


@pytest.mark.asyncio
async def test_success_never_calls_fallback_and_preserves_request():
    primary = FakeProvider([LLMStreamChunk(delta="answer"), LLMStreamChunk(done=True)])
    fallback = FakeProvider([LLMStreamChunk(delta="wrong")])
    provider = PrimaryWithFallbackProvider(primary, fallback, Settings(_env_file=None))
    events = [event async for event in provider.stream(request())]
    assert [event.delta for event in events] == ["answer", ""]
    assert len(fallback.calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [LLMTransientError("503"), LLMRateLimitError("429")])
async def test_transient_primary_failure_falls_back_with_same_context(error):
    primary = FakeProvider(error=error)
    fallback = FakeProvider([LLMStreamChunk(delta="fallback"), LLMStreamChunk(done=True)])
    provider = PrimaryWithFallbackProvider(primary, fallback, Settings(_env_file=None, LLM_FALLBACK_CHAT_MODEL="fallback-model"))
    events = [event async for event in provider.stream(request())]
    assert events[0].delta == "fallback"
    assert fallback.calls[0].messages == primary.calls[0].messages
    assert fallback.calls[0].model == "fallback-model"


@pytest.mark.asyncio
async def test_auth_or_application_failure_does_not_fall_back():
    primary = FakeProvider(error=LLMProviderError("authentication failed"))
    fallback = FakeProvider()
    provider = PrimaryWithFallbackProvider(primary, fallback, Settings(_env_file=None))
    with pytest.raises(LLMProviderError):
        async for _ in provider.stream(request()):
            pass
    assert not fallback.calls


def test_gemini_only_configuration_is_unchanged():
    settings = Settings(_env_file=None, LLM_FALLBACK_PROVIDER=None, OPENAI_API_KEY=None)
    assert settings.LLM_FALLBACK_PROVIDER is None
