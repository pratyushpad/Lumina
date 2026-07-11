from app.services.retrieval.fusion import rrf_fuse


def test_rrf_single_list_preserves_order():
    fused = rrf_fuse([["a", "b", "c"]], k=60)
    assert [cid for cid, _ in fused] == ["a", "b", "c"]
    assert fused[0][1] == 1 / 61
    assert fused[1][1] == 1 / 62


def test_rrf_item_in_both_lists_beats_single_list_top():
    # "b" is rank 2 in both lists: 1/62 + 1/62 > 1/61 (rank-1 in one list only)
    fused = rrf_fuse([["a", "b"], ["c", "b"]], k=60)
    scores = dict(fused)
    assert scores["b"] == 2 / 62
    assert fused[0][0] == "b"
    assert abs(scores["a"] - 1 / 61) < 1e-12


def test_rrf_missing_items_contribute_nothing():
    fused = rrf_fuse([["a"], []], k=60)
    assert fused == [("a", 1 / 61)]


def test_rrf_deterministic_tie_break_by_id():
    fused = rrf_fuse([["x"], ["y"]], k=60)  # equal scores
    assert [cid for cid, _ in fused] == ["x", "y"]


def test_rrf_k_dampens_rank_gap():
    small_k = rrf_fuse([["a", "b"]], k=1)
    large_k = rrf_fuse([["a", "b"]], k=1000)
    gap_small = small_k[0][1] - small_k[1][1]
    gap_large = large_k[0][1] - large_k[1][1]
    assert gap_small > gap_large
