"""Retrieval metrics computed directly (numpy only): recall@k, MRR, NDCG@10.

All functions take `retrieved` (ranked chunk ids, best first) and `relevant`
(ground-truth chunk ids, unordered; binary relevance).
"""
import numpy as np


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(retrieved[:k])
    return sum(1 for r in relevant if r in top) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    rel = set(relevant)
    for i, cid in enumerate(retrieved, start=1):
        if cid in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: list[str], k: int = 10) -> float:
    """Binary-relevance NDCG@k: DCG over the retrieved ranking divided by the
    ideal DCG (all relevant items at the top)."""
    if not relevant:
        return 0.0
    rel = set(relevant)
    gains = np.array([1.0 if cid in rel else 0.0 for cid in retrieved[:k]])
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((gains * discounts).sum())
    ideal_n = min(len(relevant), k)
    idcg = float((1.0 / np.log2(np.arange(2, ideal_n + 2))).sum())
    return dcg / idcg if idcg > 0 else 0.0


def aggregate(per_query: list[dict]) -> dict:
    """Mean of each metric key across queries."""
    if not per_query:
        return {}
    keys = per_query[0].keys()
    return {k: float(np.mean([q[k] for q in per_query])) for k in keys}
