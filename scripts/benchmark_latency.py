#!/usr/bin/env python3
"""Benchmark per-stage latency for the RAG pipeline.

Usage:
    python scripts/benchmark_latency.py [--queries N]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time

# Golden dataset queries (subset that should route to rag_knowledge_base)
BENCHMARK_QUERIES = [
    "What is the company's remote work policy?",
    "How do I report a security incident?",
    "What are the pricing tiers for enterprise plans?",
    "Summarize the key points of our security policy",
    "What is the onboarding process for new engineers?",
    "How is customer data encrypted?",
    "What monitoring tools does the company use?",
    "What are the compliance requirements for data retention?",
    "How does the company handle data deletion requests?",
    "What is the incident response process?",
    "What are the SLA terms in our service agreement?",
    "Explain the data flow described in the system architecture",
    "What troubleshooting steps are documented for database failures?",
    "What is the company's stance on AI ethics?",
    "How does our authentication system work according to the docs?",
    "Look up the deployment procedure from our runbook",
    "What does our company policy say about remote work?",
    "What are the technical requirements listed in the architecture document?",
    "Find information about the onboarding process for new employees",
    "Summarize the key points from the Q3 earnings report",
]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=20)
    args = parser.parse_args()

    # Check for API key
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("WARNING: No OPENROUTER_API_KEY — LLM generation + query expansion will fail.")
        print("Benchmark will show latency for non-LLM stages only.\n")

    from src.config.pipeline_config import load_pipeline_config
    from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
    from src.pipeline.routing import QueryRouter

    config = load_pipeline_config()
    embedding = LocalEmbeddingService(model_name=config.routing.embedding_model)

    router = QueryRouter(
        default_route=config.routing.default_route,
        confidence_threshold=config.routing.confidence_threshold,
        embed_fn=embedding.embed_texts,
    )
    await router.initialize()

    queries = BENCHMARK_QUERIES[:args.queries]
    print(f"Benchmarking {len(queries)} queries...")
    print(f"Expansion mode: {config.query_expansion.mode}")
    print(f"Expansion confidence threshold: {config.query_expansion.confidence_threshold}")
    print()

    routing_times = []
    embedding_times = []
    expansion_decisions = {"expanded": 0, "skipped": 0}

    for i, query in enumerate(queries):
        # Routing
        t0 = time.monotonic()
        result = await router.route(query)
        routing_ms = (time.monotonic() - t0) * 1000
        routing_times.append(routing_ms)

        confidence = result["confidence"]
        route = result["route"]

        # Embedding (single query)
        t0 = time.monotonic()
        _emb = await embedding.embed_texts([query])
        emb_ms = (time.monotonic() - t0) * 1000
        embedding_times.append(emb_ms)

        # Would expansion happen?
        would_expand = (
            config.query_expansion.enabled
            and config.query_expansion.mode != "never"
            and (
                config.query_expansion.mode == "always"
                or confidence < config.query_expansion.confidence_threshold
            )
        )
        if would_expand:
            expansion_decisions["expanded"] += 1
        else:
            expansion_decisions["skipped"] += 1

        print(f"  [{i+1:2d}] {query[:55]:55s} route={route:22s} conf={confidence:.2f} expand={'yes' if would_expand else 'SKIP'}")

    print()
    print("=" * 70)
    print("LATENCY SUMMARY (non-LLM stages)")
    print("=" * 70)

    def _stats(times: list[float]) -> dict[str, float]:
        s = sorted(times)
        return {
            "p50": s[len(s) // 2],
            "p95": s[int(len(s) * 0.95)],
            "mean": statistics.mean(s),
        }

    routing_stats = _stats(routing_times)
    embedding_stats = _stats(embedding_times)

    print(f"\n{'Stage':<25} | {'p50 (ms)':>10} | {'p95 (ms)':>10} | {'mean (ms)':>10}")
    print("-" * 65)
    print(f"{'Routing':<25} | {routing_stats['p50']:>10.2f} | {routing_stats['p95']:>10.2f} | {routing_stats['mean']:>10.2f}")
    print(f"{'Embedding (1 query)':<25} | {embedding_stats['p50']:>10.2f} | {embedding_stats['p95']:>10.2f} | {embedding_stats['mean']:>10.2f}")

    total = len(queries)
    print(f"\nExpansion decisions: {expansion_decisions['expanded']}/{total} expanded, {expansion_decisions['skipped']}/{total} skipped")
    pct_skipped = expansion_decisions["skipped"] / total * 100
    print(f"Expansion skip rate: {pct_skipped:.0f}% of queries skip expansion (saving ~1-3s each)")

    if pct_skipped >= 50:
        print(f"\nConditional expansion is effective: {pct_skipped:.0f}% of queries saved from LLM expansion call")
    else:
        print(f"\nConditional expansion saves {pct_skipped:.0f}% — consider lowering confidence threshold")

    # Latency budget projection
    non_llm_budget = 473  # ms from production baseline
    llm_generation = 1500  # typical LLM call
    expansion_call = 1000  # typical expansion LLM call

    # With conditional expansion
    avg_latency_conditional = non_llm_budget + llm_generation + (expansion_call * expansion_decisions["expanded"] / total)
    # Without conditional expansion (always expand)
    avg_latency_always = non_llm_budget + llm_generation + expansion_call

    print("\nProjected latency (with typical LLM times):")
    print(f"  Always expand:       ~{avg_latency_always:.0f}ms ({avg_latency_always/1000:.1f}s)")
    print(f"  Conditional expand:  ~{avg_latency_conditional:.0f}ms ({avg_latency_conditional/1000:.1f}s)")
    print(f"  Savings:             ~{avg_latency_always - avg_latency_conditional:.0f}ms ({(1 - avg_latency_conditional/avg_latency_always)*100:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
