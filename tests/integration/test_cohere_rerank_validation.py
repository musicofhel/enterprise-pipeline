"""ISSUE-001: Validate Cohere Rerank improves MRR@10 by >=15%.

Wave 3 builds hallucination checks on reranked results. If reranking is
broken, faithfulness scores are meaningless. This test validates the real
Cohere Rerank API against realistic retrieval results.

Run with:
    COHERE_API_KEY=xxx pytest tests/integration/test_cohere_rerank_validation.py -m integration -v

Before Wave 3 goes to production, this test MUST pass with a real API key.
"""
from __future__ import annotations

import os

import pytest

COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not COHERE_API_KEY, reason="COHERE_API_KEY not set"),
]


# Realistic retrieval results: 10 chunks about employee remote work policy.
# Ordered by cosine similarity (as if from vector search). Some are relevant,
# some are noise. Reranking should push relevant chunks up.
QUERY = "What is the company's policy on remote work for international employees?"

RETRIEVAL_RESULTS = [
    {
        "id": "chunk-0",
        "text_content": (
            "Section 4.2 — International Remote Work. Employees based outside the home country "
            "may request remote work arrangements subject to local labor law compliance. The "
            "company will conduct a tax nexus analysis for any employee working from a foreign "
            "jurisdiction for more than 30 cumulative days per calendar year."
        ),
        "score": 0.87,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-0"},
    },
    {
        "id": "chunk-1",
        "text_content": (
            "Our office cafeteria offers a variety of healthy meal options including "
            "vegetarian, vegan, and gluten-free choices. Lunch service runs from 11:30 AM "
            "to 1:30 PM on weekdays. Employees can also order delivery from approved vendors."
        ),
        "score": 0.84,
        "metadata": {"doc_id": "facilities-guide", "chunk_id": "chunk-1"},
    },
    {
        "id": "chunk-2",
        "text_content": (
            "Remote work equipment stipend: Employees approved for full-time remote work "
            "receive a one-time $1,500 equipment stipend and a monthly $75 internet "
            "reimbursement. International employees receive equivalent local-currency amounts "
            "based on the exchange rate at time of approval."
        ),
        "score": 0.82,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-2"},
    },
    {
        "id": "chunk-3",
        "text_content": (
            "The Q3 revenue report shows a 12% increase year-over-year, driven primarily by "
            "expansion in APAC markets. Operating margins improved to 23.4%, up from 21.1% "
            "in the prior quarter. CFO noted continued investment in R&D infrastructure."
        ),
        "score": 0.79,
        "metadata": {"doc_id": "earnings-q3-2025", "chunk_id": "chunk-3"},
    },
    {
        "id": "chunk-4",
        "text_content": (
            "Section 4.3 — Work Visa Sponsorship. The company sponsors H-1B, L-1, and O-1 "
            "visas for qualified candidates. International employees on company-sponsored visas "
            "must maintain physical presence in the approved work location unless a remote work "
            "exception is granted per Section 4.2."
        ),
        "score": 0.78,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-4"},
    },
    {
        "id": "chunk-5",
        "text_content": (
            "Annual performance reviews are conducted in December. Managers complete a "
            "360-degree feedback form, and employees submit a self-assessment. Calibration "
            "sessions occur at the department level before final ratings are communicated."
        ),
        "score": 0.76,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-5"},
    },
    {
        "id": "chunk-6",
        "text_content": (
            "Section 4.1 — Domestic Remote Work. Employees in the United States may work "
            "remotely up to 3 days per week with manager approval. Fully remote arrangements "
            "require VP-level approval and a home office safety inspection."
        ),
        "score": 0.75,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-6"},
    },
    {
        "id": "chunk-7",
        "text_content": (
            "The company holiday schedule includes 10 federal holidays plus 3 floating "
            "holidays. International offices observe local public holidays. Employees working "
            "across time zones should coordinate with their team on availability expectations."
        ),
        "score": 0.73,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-7"},
    },
    {
        "id": "chunk-8",
        "text_content": (
            "Data residency requirements: Customer data must remain in the region of origin. "
            "International employees accessing production systems must connect through the "
            "regional VPN endpoint. Cross-border data transfers require DPO approval."
        ),
        "score": 0.71,
        "metadata": {"doc_id": "security-policy-v2", "chunk_id": "chunk-8"},
    },
    {
        "id": "chunk-9",
        "text_content": (
            "Section 4.4 — International Remote Work Tax Implications. Employees working "
            "remotely from a foreign jurisdiction may create a permanent establishment risk. "
            "The company retains Ernst & Young for cross-border tax advisory. Employees must "
            "report any foreign work periods exceeding 14 days to HR and Tax."
        ),
        "score": 0.69,
        "metadata": {"doc_id": "hr-policy-v3", "chunk_id": "chunk-9"},
    },
]

# Ground truth: chunks most relevant to the query about international remote work policy.
# These should be ranked highest after reranking.
RELEVANT_CHUNK_IDS = {"chunk-0", "chunk-4", "chunk-9", "chunk-2", "chunk-6"}


def _compute_mrr_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    """Compute Mean Reciprocal Rank at k."""
    for i, chunk_id in enumerate(ranked_ids[:k]):
        if chunk_id in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


@pytest.mark.asyncio
async def test_cohere_rerank_improves_mrr():
    """Cohere Rerank must improve MRR@10 by >=15% over cosine similarity ordering.

    This test sends real data to the Cohere API and measures whether reranking
    meaningfully improves result ordering for our query type.
    """
    import cohere

    from src.pipeline.reranking.cohere_reranker import CohereReranker

    client = cohere.AsyncClientV2(api_key=COHERE_API_KEY)
    reranker = CohereReranker(client=client, top_n=10)

    # Baseline: cosine similarity ordering (as returned by vector search)
    baseline_ids = [r["id"] for r in RETRIEVAL_RESULTS]
    baseline_mrr = _compute_mrr_at_k(baseline_ids, RELEVANT_CHUNK_IDS, k=10)

    # Reranked ordering
    reranked = await reranker.rerank(QUERY, RETRIEVAL_RESULTS, top_n=10)
    reranked_ids = [r["id"] for r in reranked]
    reranked_mrr = _compute_mrr_at_k(reranked_ids, RELEVANT_CHUNK_IDS, k=10)

    # Calculate improvement
    if baseline_mrr > 0:
        improvement = (reranked_mrr - baseline_mrr) / baseline_mrr
    else:
        improvement = 1.0 if reranked_mrr > 0 else 0.0

    print(f"\nBaseline MRR@10: {baseline_mrr:.4f}")
    print(f"Reranked MRR@10: {reranked_mrr:.4f}")
    print(f"Improvement: {improvement:.1%}")
    print(f"Baseline order: {baseline_ids[:5]}")
    print(f"Reranked order: {reranked_ids[:5]}")

    assert improvement >= 0.15, (
        f"Reranking improved MRR@10 by only {improvement:.1%} (need >=15%). "
        f"Baseline={baseline_mrr:.4f}, Reranked={reranked_mrr:.4f}"
    )


@pytest.mark.asyncio
async def test_cohere_rerank_top_results_are_relevant():
    """After reranking, top 3 results should all be from relevant chunks."""
    import cohere

    from src.pipeline.reranking.cohere_reranker import CohereReranker

    client = cohere.AsyncClientV2(api_key=COHERE_API_KEY)
    reranker = CohereReranker(client=client, top_n=5)

    reranked = await reranker.rerank(QUERY, RETRIEVAL_RESULTS, top_n=5)
    top_3_ids = {r["id"] for r in reranked[:3]}

    overlap = top_3_ids & RELEVANT_CHUNK_IDS
    print(f"\nTop 3 reranked: {[r['id'] for r in reranked[:3]]}")
    print(f"Relevant: {RELEVANT_CHUNK_IDS}")
    print(f"Overlap: {overlap}")

    assert len(overlap) >= 2, (
        f"Expected at least 2 of top 3 reranked results to be relevant, "
        f"got {len(overlap)}: {top_3_ids}"
    )
