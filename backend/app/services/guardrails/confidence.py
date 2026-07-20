"""Refusal gate: when retrieval confidence is low, say so instead of guessing.

Two-stage gate. Stage 1: the cross-encoder reranker's sigmoid-normalized top
score is the primary confidence signal — above MIN_RERANK_SCORE the answer
proceeds (false-refusal and false-answer rates at this threshold are measured
in docs/eval.md). Stage 2: cross-encoders score literal matches high but can
under-score honest paraphrases (query "salary" against a chunk saying
"annualized base compensation"). So before refusing, the gate re-checks the
top candidates with the bi-encoder: cosine similarity between the query
embedding and the candidate texts. Only when BOTH signals are weak does the
gate refuse — synonym-phrased questions pass to the LLM, whose grounding
prompt and citations remain the final defense.
"""
import logging

from app.config import settings
from app.services.embedding.embedder import EmbeddingService
from app.services.retrieval.types import RetrievalResult

logger = logging.getLogger("lumina.guardrails")

REFUSAL_MESSAGE = (
    "I couldn't find anything in your documents that answers this question. "
    "The retrieved passages scored too low to be trustworthy evidence, so rather "
    "than guess, I'm saying so. Try rephrasing, or upload a document that covers this topic."
)

_SECOND_CHANCE_TOP_N = 5


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=True))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def should_refuse(results: list[RetrievalResult], query: str | None = None) -> bool:
    if not settings.GUARDRAIL_REFUSAL_ENABLED:
        return False
    if not results:
        return True
    if max(r.relevance_score for r in results) >= settings.MIN_RERANK_SCORE:
        return False

    # Stage 2: paraphrase second chance on the bi-encoder signal. The stored
    # `distance` field is 0.0 for sparse-path candidates, so similarity is
    # recomputed here (local model, only on the would-refuse path).
    if query is None:
        return True
    try:
        embedder = EmbeddingService.get()
        q_vec = embedder.embed_query(query)
        texts = [r.text for r in results[:_SECOND_CHANCE_TOP_N]]
        sims = [_cosine(q_vec, v) for v in embedder.embed_texts(texts)]
        best = max(sims, default=0.0)
        logger.info(
            "second-chance gate: rerank below %.2f, best bi-encoder sim %.3f (min %.2f)",
            settings.MIN_RERANK_SCORE, best, settings.MIN_BIENCODER_SIM,
        )
        return best < settings.MIN_BIENCODER_SIM
    except Exception:
        logger.exception("second-chance similarity failed; falling back to refusal")
        return True
