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
        self, query: str, results: list[RetrievalResult], top_k: Optional[int] = None
    ) -> list[RetrievalResult]:
        if not results:
            return []
        top_k = top_k or settings.TOP_K_RERANKED
        pairs = [(query, r.text) for r in results]
        scores = self.model.predict(pairs)
        for r, s in zip(results, scores):
            r.relevance_score = float(s)
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        # Always keep top_k. Only drop tail results whose sigmoid-normalized score is
        # below a soft noise floor (0.1 ~= raw score -2.2). This avoids returning an
        # empty context when raw logits are low across the board.
        top = results[:top_k]
        for r in top:
            r.relevance_score = _sigmoid(r.relevance_score)
        return [r for r in top if r.relevance_score >= 0.1] or top[:1]
