from __future__ import annotations

from typing import Any


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse multiple ranked result lists using Reciprocal Rank Fusion.

    For each document appearing across the result lists, the fused score is:

        score(d) = sum( 1 / (k + rank_i(d)) )

    where rank_i(d) is the 1-based rank of document d in result list i (or
    absent if d does not appear in that list).

    Args:
        result_lists: A list of ranked result lists. Each result dict must
            contain an ``"id"`` key used for deduplication.
        k: The RRF constant (default 60). Higher values dampen the influence
            of high-ranked items.

    Returns:
        A single list of result dicts sorted by fused score descending.
        Each dict has an ``"rrf_score"`` field attached.
    """
    if not result_lists:
        return []

    # Accumulate RRF scores keyed by document id
    scores: dict[str, float] = {}
    # Keep the first occurrence of each document for its payload
    docs: dict[str, dict[str, Any]] = {}

    for result_list in result_lists:
        for rank_zero_based, result in enumerate(result_list):
            doc_id = result["id"]
            rank = rank_zero_based + 1  # 1-based rank
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

            if doc_id not in docs:
                docs[doc_id] = result

    # Attach rrf_score and sort descending
    fused: list[dict[str, Any]] = []
    for doc_id, score in scores.items():
        entry = {**docs[doc_id], "rrf_score": score}
        fused.append(entry)

    fused.sort(key=lambda d: d["rrf_score"], reverse=True)
    return fused
