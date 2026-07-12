"""Provider interface for LLM generation (local GPU box or hosted API)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Union


@dataclass
class GenResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    duration_s: float
    provider: str
    model: str
    tokens_estimated: bool = False  # True when the backend returned no usage data

    @property
    def tokens_per_sec(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return self.completion_tokens / self.duration_s

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


# Streaming yields str tokens, then exactly one final GenResult with timing/usage.
StreamEvent = Union[str, GenResult]


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def generate(self, system: str, user: str) -> GenResult: ...

    @abstractmethod
    def generate_stream(self, system: str, user: str) -> AsyncGenerator[StreamEvent, None]: ...

    @abstractmethod
    async def health(self) -> bool: ...
