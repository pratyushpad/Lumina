"""GeminiProvider against the google-genai >= 1.0 async API shape, with no network.

The real SDK's `aio.models.generate_content_stream` is a coroutine returning an
AsyncIterator. These tests fake that exact shape so a regression to the 0.x calling
convention (iterating the coroutine directly) fails here instead of in production.
"""
import inspect
from types import SimpleNamespace

import pytest
from google.genai import models

from app.config import settings
from app.services.generation.providers.base import GenResult
from app.services.generation.providers.gemini import GeminiProvider


def test_sdk_stream_is_awaitable():
    # Guards the assumption the fake below encodes.
    assert inspect.iscoroutinefunction(models.AsyncModels.generate_content_stream)


def _chunk(text, tokens=None):
    usage = SimpleNamespace(candidates_token_count=tokens) if tokens else None
    return SimpleNamespace(text=text, usage_metadata=usage)


class _FakeAioModels:
    async def generate_content_stream(self, *, model, contents, config):
        async def gen():
            yield _chunk("Hello ")
            yield _chunk("world", tokens=2)

        return gen()

    async def generate_content(self, *, model, contents, config):
        usage = SimpleNamespace(prompt_token_count=7, candidates_token_count=3)
        return SimpleNamespace(text="Hi there", usage_metadata=usage)


@pytest.fixture
def _provider(monkeypatch):
    # The SDK client refuses to construct without a key; a dummy one never leaves
    # the process because the client is replaced before any call.
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key-not-real")
    p = GeminiProvider()
    p.client = SimpleNamespace(aio=SimpleNamespace(models=_FakeAioModels()))
    return p


async def test_generate_stream_yields_tokens_then_result(_provider):
    events = [e async for e in _provider.generate_stream("sys", "q")]
    assert events[:2] == ["Hello ", "world"]
    final = events[-1]
    assert isinstance(final, GenResult)
    assert final.text == "Hello world"
    assert final.completion_tokens == 2
    assert final.tokens_estimated is False


async def test_generate_returns_usage(_provider):
    res = await _provider.generate("sys", "q")
    assert res.text == "Hi there"
    assert (res.prompt_tokens, res.completion_tokens) == (7, 3)
