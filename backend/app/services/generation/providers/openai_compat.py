"""OpenAI-compatible provider: one class covers Ollama (`/v1`) and vLLM.

Points at the GPU box over the LAN (e.g. LOCAL_LLM_BASE_URL=http://gpu-box:11434/v1
for Ollama — remember `OLLAMA_HOST=0.0.0.0` plus a firewall rule on the box), or at
a local `ollama serve` for development. Tokens/sec is measured from streamed chunk
timestamps and the backend's reported usage.
"""
import json
import logging
import time
from typing import AsyncGenerator, Optional

import httpx

from app.config import settings
from app.services.generation.providers.base import GenResult, LLMProvider, StreamEvent
from app.utils.text_utils import estimate_tokens

logger = logging.getLogger("lumina.providers.local")


class OpenAICompatProvider(LLMProvider):
    name = "local"

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.LOCAL_LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LOCAL_LLM_MODEL
        self.timeout = httpx.Timeout(settings.LOCAL_LLM_TIMEOUT_S, connect=3.0)
        # Optional Bearer auth: lets this provider target hosted OpenAI-compatible
        # endpoints (Groq, Cerebras, Mistral, …) — Ollama/vLLM ignore a missing key.
        self.headers = (
            {"Authorization": f"Bearer {settings.LOCAL_LLM_API_KEY}"}
            if settings.LOCAL_LLM_API_KEY
            else {}
        )

    def _payload(self, system: str, user: str, stream: bool) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    async def generate(self, system: str, user: str) -> GenResult:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=self._payload(system, user, False),
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
        duration = time.perf_counter() - t0
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        return GenResult(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", estimate_tokens(text)),
            duration_s=duration,
            provider=self.name,
            model=self.model,
            tokens_estimated="completion_tokens" not in usage,
        )

    async def generate_stream(self, system: str, user: str) -> AsyncGenerator[StreamEvent, None]:
        t0 = time.perf_counter()
        parts: list[str] = []
        usage: dict = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=self._payload(system, user, True),
                headers=self.headers,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        token = delta.get("content")
                        if token:
                            parts.append(token)
                            yield token
        text = "".join(parts)
        yield GenResult(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", estimate_tokens(text)),
            duration_s=time.perf_counter() - t0,
            provider=self.name,
            model=self.model,
            tokens_estimated="completion_tokens" not in usage,
        )

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self.headers)
                return resp.status_code == 200
        except Exception:
            return False
