"""Query transformations: multi-query rewriting and HyDE, via the LLM service."""
import logging

from app.services.generation.llm import LLMService

logger = logging.getLogger("lumina.query_transform")

_MULTI_QUERY_SYSTEM = (
    "You rewrite search queries. Given a user question, produce 3 alternative "
    "phrasings that would retrieve the same information from a document corpus. "
    "Vary vocabulary and specificity. Output ONLY the 3 rewrites, one per line, "
    "no numbering, no commentary."
)

_HYDE_SYSTEM = (
    "Write a short, factual passage (3-5 sentences) that would plausibly appear in a "
    "document answering the user's question. Do not address the user; write it as "
    "document prose. Output only the passage."
)


async def multi_query(query: str, n: int = 3) -> list[str]:
    """Return the original query plus up to n LLM rewrites (falls back to just the query)."""
    try:
        text, _ = await LLMService.get().generate(_MULTI_QUERY_SYSTEM, query)
        rewrites = []
        for line in text.splitlines():
            line = line.strip().lstrip("0123456789.-) ").strip()
            if line and line.lower() != query.lower():
                rewrites.append(line)
        return [query] + rewrites[:n]
    except Exception:
        logger.exception("multi_query rewrite failed; using original query only")
        return [query]


async def hyde(query: str) -> str:
    """Return a hypothetical document passage to embed instead of the raw query."""
    try:
        text, _ = await LLMService.get().generate(_HYDE_SYSTEM, query)
        return text.strip() or query
    except Exception:
        logger.exception("HyDE generation failed; using original query")
        return query
