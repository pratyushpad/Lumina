"""Reciprocal Rank Fusion over ranked id lists (pure functions, unit-tested)."""


def rrf_fuse(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Fuse ranked lists of ids: score(id) = sum over lists of 1/(k + rank), rank 1-based.

    Ids missing from a list contribute nothing for that list. Returns ids sorted by
    fused score descending; ties broken by id for determinism.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
