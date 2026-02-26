#!/usr/bin/env python3
"""Validate routing accuracy against a labeled test set.

Usage:
    python scripts/validate_routing.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Routing test cases: (query, expected_route)
ROUTING_TEST_CASES: list[tuple[str, str]] = [
    # rag_knowledge_base (8 cases)
    ("What is the company's remote work policy?", "rag_knowledge_base"),
    ("How do I report a security incident?", "rag_knowledge_base"),
    ("What are the pricing tiers?", "rag_knowledge_base"),
    ("Summarize the key points of our security policy", "rag_knowledge_base"),
    ("What is the company's policy on quantum computing?", "rag_knowledge_base"),
    ("Compare our pricing to competitors", "rag_knowledge_base"),
    ("What is the onboarding process for new engineers?", "rag_knowledge_base"),
    ("How is customer data encrypted?", "rag_knowledge_base"),
    # direct_llm (4 cases)
    ("What is 2 + 2?", "direct_llm"),
    ("Write me a haiku about clouds", "direct_llm"),
    ("Help me brainstorm names for our new feature", "direct_llm"),
    ("Draft a professional email declining a meeting", "direct_llm"),
    # escalate_human (4 cases)
    ("I want to file a formal complaint", "escalate_human"),
    ("I need to speak with a human representative", "escalate_human"),
    ("I am considering legal action against the company", "escalate_human"),
    ("I want to report workplace harassment to HR", "escalate_human"),
    # sql_structured_data (2 cases)
    ("How many active users do we have this month?", "sql_structured_data"),
    ("Show me the revenue breakdown by region for Q4", "sql_structured_data"),
    # api_lookup (2 cases)
    ("What is the current status of the production deployment?", "api_lookup"),
    ("Check if the payment gateway is operational right now", "api_lookup"),
]


async def main() -> None:
    from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
    from src.pipeline.routing import QueryRouter

    embedding = LocalEmbeddingService(model_name="all-MiniLM-L6-v2")

    router = QueryRouter(
        default_route="rag_knowledge_base",
        confidence_threshold=0.5,
        routes_path=Path("src/pipeline/routing/routes.yaml"),
        embed_fn=embedding.embed_texts,
    )
    await router.initialize()

    # Group by expected route
    by_route: dict[str, list[tuple[str, str]]] = {}
    for query, expected in ROUTING_TEST_CASES:
        by_route.setdefault(expected, []).append((query, expected))

    total = 0
    correct = 0
    failures: list[tuple[str, str, str, float]] = []

    for route_name in sorted(by_route.keys()):
        print(f"\nRoute: {route_name}")
        for query, expected in by_route[route_name]:
            result = await router.route(query)
            actual = result["route"]
            conf = result["confidence"]
            all_scores = result["scores"]
            ok = actual == expected
            total += 1
            if ok:
                correct += 1
                print(f"  \u2713 \"{query[:60]}\" \u2192 {actual} ({conf:.2f})")
            else:
                failures.append((query, expected, actual, conf))
                print(f"  \u2717 \"{query[:60]}\" \u2192 {actual} ({conf:.2f}) [expected {expected}]")
                # Show all route scores for debugging
                sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
                for rname, rscore in sorted_scores:
                    marker = " <--" if rname == expected else ""
                    print(f"      {rname}: {rscore:.4f}{marker}")

    pct = correct / total * 100
    print(f"\n{'=' * 60}")
    print(f"Accuracy: {correct}/{total} ({pct:.0f}%)")
    print(f"{'=' * 60}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for query, expected, actual, conf in failures:
            print(f"  \"{query[:60]}\" expected={expected} got={actual} conf={conf:.2f}")

    target = 90
    if pct >= target:
        print(f"\nPASS: routing accuracy {pct:.0f}% >= {target}% target")
    else:
        print(f"\nFAIL: routing accuracy {pct:.0f}% < {target}% target")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
