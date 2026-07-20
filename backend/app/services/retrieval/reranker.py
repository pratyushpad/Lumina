"""Cross-encoder reranker singleton."""
import logging
import math
from typing import Optional

from sentence_transformers import CrossEncoder

from app.config import settings
from app.services.retrieval.types import RetrievalResult

logger = logging.getLogger("lumina.reranker")


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


class Reranker:
    _instance: Optional["Reranker"] = None

    def __init__(self):
        logger.info("Loading reranker model: %s", settings.RERANKER_MODEL)
        self.model = CrossEncoder(settings.RERANKER_MODEL)
        logger.info("Reranker ready")

    @classmethod
    def get(cls) -> "Reranker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def rerank(
        self, query: str, results: list[RetrievalResult], top_k: int | None = None
    ) -> list[RetrievalResult]:
        if not results:
            return []
        top_k = top_k or settings.TOP_K_RERANKED
        fused_order = list(results)  # upstream hybrid/RRF ranking, best-first
        pairs = [(query, r.text) for r in results]
        scores = self.model.predict(pairs)
        for r, s in zip(results, scores, strict=True):
            r.relevance_score = _sigmoid(float(s))
        ranked = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        # Cross-encoders can zero out every pair on paraphrase/typo queries
        # ("salary" vs a chunk saying "compensation"). When the model is uniformly
        # unconfident, its ordering is noise — promoting arbitrary chunks and
        # starving generation of the right context. Fall back to the fused
        # retrieval order instead of trusting a signal that has nothing to say.
        if not ranked or ranked[0].relevance_score < settings.MIN_RERANK_SCORE:
            logger.info(
                "reranker unconfident (max %.3f < %.2f); keeping fused retrieval order",
                ranked[0].relevance_score if ranked else 0.0,
                settings.MIN_RERANK_SCORE,
            )
            return fused_order[:top_k]
        # Confident path: keep top_k, dropping tail results below a soft noise
        # floor (0.1 ~= raw score -2.2) so context stays clean without ever
        # returning empty.
        top = ranked[:top_k]
        return [r for r in top if r.relevance_score >= 0.1] or top[:1]
