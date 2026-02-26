"""ISSUE-004: Test routing accuracy with real local embeddings."""
from __future__ import annotations

import asyncio
import time


async def test_routing() -> list[dict]:
    from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
    from src.pipeline.routing import QueryRouter

    local_emb = LocalEmbeddingService()
    router = QueryRouter(embed_fn=local_emb.embed_texts, confidence_threshold=0.15)

    test_cases = [
        ("What is the company's remote work policy?", "rag_knowledge_base"),
        ("How do I report a security incident?", "rag_knowledge_base"),
        ("What are the pricing tiers?", "rag_knowledge_base"),
        ("I need to speak with a human immediately", "escalate_human"),
        ("Write me a professional email", "direct_llm"),
    ]

    results = []
    correct = 0
    for query, expected in test_cases:
        start = time.monotonic()
        result = await router.route(query)
        latency_ms = (time.monotonic() - start) * 1000
        actual = result["route"]
        match = actual == expected
        if match:
            correct += 1
        results.append({
            "query": query,
            "expected": expected,
            "actual": actual,
            "confidence": result["confidence"],
            "match": match,
            "latency_ms": round(latency_ms, 1),
            "all_scores": result["scores"],
        })

    print(f"\nRouting Accuracy: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.0f}%)")
    print()
    for r in results:
        status = "PASS" if r["match"] else "FAIL"
        print(f'  [{status}] "{r["query"]}"')
        print(f'         Expected: {r["expected"]}  Actual: {r["actual"]}  Confidence: {r["confidence"]}')
        print(f'         Scores: {r["all_scores"]}  Latency: {r["latency_ms"]}ms')
        print()

    return results


if __name__ == "__main__":
    asyncio.run(test_routing())
