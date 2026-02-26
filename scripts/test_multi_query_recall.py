"""ISSUE-005: Test multi-query recall with live Qdrant."""
from __future__ import annotations

import asyncio
import time


async def test_multi_query_recall() -> None:
    from qdrant_client import AsyncQdrantClient

    from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
    from src.pipeline.retrieval.vector_store import VectorStore

    client = AsyncQdrantClient(url="http://localhost:6333")
    vs = VectorStore(client=client)
    emb = LocalEmbeddingService()

    query = "What is the company policy on remote work?"

    # Single query retrieval
    start = time.monotonic()
    single_emb = await emb.embed_query(query)
    single_results = await vs.search(query_embedding=single_emb, top_k=10)
    single_latency = (time.monotonic() - start) * 1000

    # Multi-query: manually expand
    expanded_queries = [
        query,
        "remote work policy for employees",
        "working from home guidelines and rules",
        "telecommuting arrangements and procedures",
    ]

    start = time.monotonic()
    all_results = []
    seen_ids: set[str] = set()
    for q in expanded_queries:
        q_emb = await emb.embed_query(q)
        q_results = await vs.search(query_embedding=q_emb, top_k=10)
        for r in q_results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)
    multi_latency = (time.monotonic() - start) * 1000

    # Sort multi results by score desc
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    print("\n=== Multi-Query Recall Test ===")
    print(f"Single query: {len(single_results)} results, {single_latency:.0f}ms")
    print(f"Multi query ({len(expanded_queries)} queries): {len(all_results)} unique results, {multi_latency:.0f}ms")
    print(f"Recall improvement: {len(all_results) - len(single_results)} additional unique results")
    print()
    print("Single query top 5:")
    for r in single_results[:5]:
        snippet = r.get("text_content", "")[:100]
        print(f'  [{r["score"]:.4f}] {snippet}...')
    print()
    print("Multi-query top 5 (deduplicated):")
    for r in all_results[:5]:
        snippet = r.get("text_content", "")[:100]
        print(f'  [{r.get("score", 0):.4f}] {snippet}...')

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_multi_query_recall())
