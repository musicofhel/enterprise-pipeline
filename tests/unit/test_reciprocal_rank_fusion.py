from __future__ import annotations

from src.pipeline.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion


def _make_result(doc_id: str, text: str = "", score: float = 0.9) -> dict:
    return {"id": doc_id, "text_content": text, "score": score, "metadata": {}}


# ---- Tests ----


def test_empty_input_returns_empty():
    assert reciprocal_rank_fusion([]) == []


def test_single_list_preserves_order():
    """A single result list should come back in the same order."""
    results = [
        _make_result("a", score=0.95),
        _make_result("b", score=0.80),
        _make_result("c", score=0.70),
    ]
    fused = reciprocal_rank_fusion([results])

    assert [r["id"] for r in fused] == ["a", "b", "c"]


def test_rrf_score_attached():
    """Every result should have an rrf_score key."""
    results = [_make_result("a"), _make_result("b")]
    fused = reciprocal_rank_fusion([results])

    for r in fused:
        assert "rrf_score" in r
        assert isinstance(r["rrf_score"], float)
        assert r["rrf_score"] > 0


def test_deduplication_by_id():
    """Documents appearing in multiple lists should be merged, not duplicated."""
    list_a = [_make_result("x"), _make_result("y")]
    list_b = [_make_result("y"), _make_result("z")]

    fused = reciprocal_rank_fusion([list_a, list_b])
    ids = [r["id"] for r in fused]

    assert len(ids) == 3
    assert set(ids) == {"x", "y", "z"}


def test_fused_order_is_correct():
    """A document ranked highly in both lists should beat one ranked highly in only one."""
    #  list_a: doc_1 (rank 1), doc_2 (rank 2)
    #  list_b: doc_1 (rank 1), doc_3 (rank 2)
    # doc_1 appears at rank 1 in both lists → highest RRF score
    list_a = [_make_result("doc_1"), _make_result("doc_2")]
    list_b = [_make_result("doc_1"), _make_result("doc_3")]

    fused = reciprocal_rank_fusion([list_a, list_b], k=60)

    assert fused[0]["id"] == "doc_1"
    # doc_1: 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.03279
    # doc_2: 1/(60+2) = 1/62 ≈ 0.01613
    # doc_3: 1/(60+2) = 1/62 ≈ 0.01613
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_rrf_scores_are_mathematically_correct():
    """Verify exact RRF score computation with known values."""
    k = 60
    list_a = [_make_result("a"), _make_result("b")]  # a=rank1, b=rank2
    list_b = [_make_result("b"), _make_result("c")]  # b=rank1, c=rank2

    fused = reciprocal_rank_fusion([list_a, list_b], k=k)
    scores = {r["id"]: r["rrf_score"] for r in fused}

    # a: only in list_a at rank 1 → 1/(60+1)
    assert abs(scores["a"] - 1.0 / 61) < 1e-10
    # b: list_a rank 2 + list_b rank 1 → 1/(60+2) + 1/(60+1)
    assert abs(scores["b"] - (1.0 / 62 + 1.0 / 61)) < 1e-10
    # c: only in list_b at rank 2 → 1/(60+2)
    assert abs(scores["c"] - 1.0 / 62) < 1e-10


def test_custom_k_parameter():
    """Different k values should produce different scores."""
    results = [_make_result("a"), _make_result("b")]

    fused_low_k = reciprocal_rank_fusion([results], k=1)
    fused_high_k = reciprocal_rank_fusion([results], k=1000)

    # With lower k, rank-1 score is higher relative to rank-2
    ratio_low_k = fused_low_k[0]["rrf_score"] / fused_low_k[1]["rrf_score"]
    ratio_high_k = fused_high_k[0]["rrf_score"] / fused_high_k[1]["rrf_score"]

    # Lower k means bigger gap between rank 1 and rank 2
    assert ratio_low_k > ratio_high_k


def test_preserves_original_fields():
    """Fused results should retain all original dict fields."""
    result = {"id": "abc", "text_content": "hello world", "score": 0.95, "metadata": {"key": "val"}}
    fused = reciprocal_rank_fusion([[result]])

    assert fused[0]["text_content"] == "hello world"
    assert fused[0]["score"] == 0.95
    assert fused[0]["metadata"] == {"key": "val"}


def test_three_lists_with_overlap():
    """Three result lists with partial overlap should fuse correctly."""
    list_a = [_make_result("1"), _make_result("2"), _make_result("3")]
    list_b = [_make_result("2"), _make_result("3"), _make_result("4")]
    list_c = [_make_result("3"), _make_result("4"), _make_result("5")]

    fused = reciprocal_rank_fusion([list_a, list_b, list_c], k=60)

    ids = [r["id"] for r in fused]
    assert set(ids) == {"1", "2", "3", "4", "5"}

    # doc "3" appears in all 3 lists (rank3, rank2, rank1) — should have highest score
    scores = {r["id"]: r["rrf_score"] for r in fused}
    assert scores["3"] == max(scores.values())


def test_single_empty_list():
    """A list containing one empty result list should return empty."""
    assert reciprocal_rank_fusion([[]]) == []
