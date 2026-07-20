"""Hosted Gemini provider (also the fallback when the local GPU box is offline)."""
import logging
import time
from collections.abc import AsyncGenerator

from google import genai
from google.genai import types

from app.config import settings
from app.services.generation.providers.base import GenResult, LLMProvider, StreamEvent
from app.utils.text_utils import estimate_tokens

logger = logging.getLogger("lumina.providers.gemini")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.LLM_MODEL

    def _config(self, system: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=settings.LLM_MAX_TOKENS,
            temperature=0.2,
        )

    async def generate(self, system: str, user: str) -> GenResult:
        t0 = time.perf_counter()
        resp = await self.client.aio.models.generate_content(
            model=self.model, contents=user, config=self._config(system)
        )
        duration = time.perf_counter() - t0
        text = resp.text or ""
        usage = resp.usage_metadata
        return GenResult(
            text=text,
            prompt_tokens=(usage.prompt_token_count or 0) if usage else 0,
            completion_tokens=(usage.candidates_token_count or 0) if usage else estimate_tokens(text),
            duration_s=duration,
            provider=self.name,
            model=self.model,
            tokens_estimated=usage is None,
        )

    async def generate_stream(self, system: str, user: str) -> AsyncGenerator[StreamEvent, None]:
        t0 = time.perf_counter()
        parts: list[str] = []
        completion_tokens = 0
        # generate_content_stream is an async-generator function — do NOT await it.
        async for chunk in self.client.aio.models.generate_content_stream(
            model=self.model, contents=user, config=self._config(system)
        ):
            if chunk.text:
                parts.append(chunk.text)
                yield chunk.text
            if chunk.usage_metadata and chunk.usage_metadata.candidates_token_count:
                completion_tokens = chunk.usage_metadata.candidates_token_count
        text = "".join(parts)
        yield GenResult(
            text=text,
            prompt_tokens=0,
            completion_tokens=completion_tokens or estimate_tokens(text),
            duration_s=time.perf_counter() - t0,
            provider=self.name,
            model=self.model,
            tokens_estimated=completion_tokens == 0,
        )

    async def health(self) -> bool:
        # Hosted API: consider available whenever a key is configured; actual
        # failures surface per-request and trigger router fallback.
        return bool(settings.GEMINI_API_KEY)
