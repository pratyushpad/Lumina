"""LLM façade over the provider router (local GPU serving with hosted fallback).

Back-compat surface (generate -> (text, tokens), generate_stream -> str tokens)
is kept for existing callers; new callers that need provider/timing metadata use
generate_result / generate_stream_events.
"""
import logging
from collections.abc import AsyncGenerator
from typing import Optional

from app.services.generation.providers.base import GenResult, StreamEvent
from app.services.generation.providers.router import ProviderRouter

logger = logging.getLogger("lumina.llm")


class LLMService:
    _instance: Optional["LLMService"] = None

    def __init__(self):
        self.router = ProviderRouter.get()

    @classmethod
    def get(cls) -> "LLMService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def generate(self, system: str, user: str) -> tuple[str, int]:
        r = await self.router.generate(system, user)
        return r.text, r.prompt_tokens + r.completion_tokens

    async def generate_result(self, system: str, user: str) -> GenResult:
        return await self.router.generate(system, user)

    async def generate_stream(self, system: str, user: str) -> AsyncGenerator[str, None]:
        async for ev in self.router.generate_stream(system, user):
            if isinstance(ev, str):
                yield ev

    async def generate_stream_events(
        self, system: str, user: str
    ) -> AsyncGenerator[StreamEvent, None]:
        async for ev in self.router.generate_stream(system, user):
            yield ev
