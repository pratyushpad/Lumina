"""Provider router: ordered fallback (e.g. local GPU first, hosted Gemini second).

Health checks are cached with a short TTL so a dead local box costs at most one
2-second probe per TTL window; per-request errors also trigger fallback to the
next provider in the order.
"""
import logging
import time
from collections.abc import AsyncGenerator

from app.config import settings
from app.services.generation.providers.base import GenResult, LLMProvider, StreamEvent
from app.services.generation.providers.gemini import GeminiProvider
from app.services.generation.providers.openai_compat import OpenAICompatProvider

logger = logging.getLogger("lumina.providers.router")


class AllProvidersFailedError(Exception):
    """Every configured LLM provider failed (usually free-tier rate limits).

    The message carries provider internals for logs; API error handlers must map
    this to a clean 503 without exposing the detail to clients.
    """

_HEALTH_TTL_S = 30.0


class ProviderRouter:
    _instance = None

    def __init__(self):
        registry = {"gemini": GeminiProvider, "local": OpenAICompatProvider}
        order = [p.strip() for p in settings.LLM_PROVIDER_ORDER.split(",") if p.strip()]
        self.providers: list[LLMProvider] = []
        for name in order:
            if name not in registry:
                raise ValueError(f"Unknown LLM provider {name!r} in LLM_PROVIDER_ORDER")
            self.providers.append(registry[name]())
        if not self.providers:
            raise ValueError("LLM_PROVIDER_ORDER is empty")
        self._health: dict[str, tuple[float, bool]] = {}  # name -> (checked_at, ok)

    @classmethod
    def get(cls) -> "ProviderRouter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _healthy(self, p: LLMProvider) -> bool:
        now = time.monotonic()
        cached = self._health.get(p.name)
        if cached and now - cached[0] < _HEALTH_TTL_S:
            return cached[1]
        ok = await p.health()
        self._health[p.name] = (now, ok)
        if not ok:
            logger.info("Provider %s unhealthy; will retry in %ss", p.name, _HEALTH_TTL_S)
        return ok

    def _mark_down(self, p: LLMProvider) -> None:
        self._health[p.name] = (time.monotonic(), False)

    async def _candidates(self) -> list[LLMProvider]:
        healthy = [p for p in self.providers if await self._healthy(p)]
        # Never return an empty list: if everything looks down, try them all anyway.
        return healthy or list(self.providers)

    async def generate(self, system: str, user: str) -> GenResult:
        candidates = await self._candidates()
        last_err: Exception | None = None
        for i, p in enumerate(candidates):
            try:
                return await p.generate(system, user)
            except Exception as e:
                last_err = e
                self._mark_down(p)
                if i < len(candidates) - 1:
                    logger.warning("Provider %s failed (%s); falling back", p.name, e)
        raise AllProvidersFailedError(str(last_err)) from last_err

    async def generate_stream(self, system: str, user: str) -> AsyncGenerator[StreamEvent, None]:
        """Falls back only if a provider fails BEFORE emitting any token (once tokens
        have streamed to the client, switching providers mid-answer is worse than
        surfacing the error)."""
        candidates = await self._candidates()
        last_err: Exception | None = None
        for i, p in enumerate(candidates):
            emitted = False
            try:
                async for ev in p.generate_stream(system, user):
                    emitted = True
                    yield ev
                return
            except Exception as e:
                self._mark_down(p)
                if emitted:
                    raise
                if i == len(candidates) - 1:
                    raise AllProvidersFailedError(str(e)) from e
                last_err = e
                logger.warning("Provider %s failed pre-stream (%s); falling back", p.name, e)
        if last_err:
            raise AllProvidersFailedError(str(last_err)) from last_err
