"""ISSUE-002 + ISSUE-006: Capture latency baselines from real pipeline execution."""
from __future__ import annotations

import asyncio
import json
import time


async def capture_baselines() -> dict:
    """Run pipeline stages individually and capture latency for each."""
    from qdrant_client import AsyncQdrantClient

    from src.pipeline.compression.bm25_compressor import BM25Compressor
    from src.pipeline.compression.token_budget import TokenBudgetEnforcer
    from src.pipeline.quality import HallucinationChecker
    from src.pipeline.retrieval.deduplication import Deduplicator
    from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
    from src.pipeline.retrieval.vector_store import VectorStore
    from src.pipeline.routing import QueryRouter
    from src.pipeline.safety import SafetyChecker
    from src.pipeline.safety.injection_detector import InjectionDetector
    from src.pipeline.safety.pii_detector import PIIDetector

    baselines: dict[str, dict] = {}
    query = "What is the company policy on remote work?"

    # 1. Safety (L1 regex + PII)
    checker = SafetyChecker(
        injection_detector=InjectionDetector(),
        pii_detector=PIIDetector(),
    )
    start = time.monotonic()
    safety_result = await checker.check_input(query, user_id="baseline-test")
    safety_latency = (time.monotonic() - start) * 1000
    baselines["safety_l1_pii"] = {
        "latency_ms": round(safety_latency, 2),
        "passed": safety_result["passed"],
    }

    # 2. Routing (local embeddings)
    local_emb = LocalEmbeddingService()
    router = QueryRouter(embed_fn=local_emb.embed_texts, confidence_threshold=0.15)

    # Warm up (first call includes model loading)
    await router.route("warmup query")

    start = time.monotonic()
    route_result = await router.route(query)
    routing_latency = (time.monotonic() - start) * 1000
    baselines["routing"] = {
        "latency_ms": round(routing_latency, 2),
        "route": route_result["route"],
        "confidence": route_result["confidence"],
    }

    # 3. Embedding (single query)
    start = time.monotonic()
    query_emb = await local_emb.embed_query(query)
    embed_latency = (time.monotonic() - start) * 1000
    baselines["embedding_single_query"] = {
        "latency_ms": round(embed_latency, 2),
        "dimensions": len(query_emb),
    }

    # 4. Retrieval (Qdrant)
    client = AsyncQdrantClient(url="http://localhost:6333")
    vs = VectorStore(client=client)

    start = time.monotonic()
    results = await vs.search(query_embedding=query_emb, top_k=20)
    retrieval_latency = (time.monotonic() - start) * 1000
    baselines["retrieval_qdrant"] = {
        "latency_ms": round(retrieval_latency, 2),
        "results_count": len(results),
        "top_k": 20,
    }

    # 5. Deduplication
    dedup = Deduplicator(threshold=0.95)
    start = time.monotonic()
    deduped = dedup.deduplicate(results)
    dedup_latency = (time.monotonic() - start) * 1000
    baselines["deduplication"] = {
        "latency_ms": round(dedup_latency, 2),
        "before": len(results),
        "after": len(deduped),
    }

    # 6. BM25 Compression
    compressor = BM25Compressor()
    start = time.monotonic()
    compressed = compressor.compress(query, deduped)
    compression_latency = (time.monotonic() - start) * 1000
    baselines["bm25_compression"] = {
        "latency_ms": round(compression_latency, 2),
        "before": len(deduped),
        "after": len(compressed),
    }

    # 7. Token Budget
    budget = TokenBudgetEnforcer(max_tokens=3000)
    start = time.monotonic()
    budgeted = budget.enforce(compressed)
    budget_latency = (time.monotonic() - start) * 1000
    baselines["token_budget"] = {
        "latency_ms": round(budget_latency, 2),
        "chunks_after": len(budgeted),
    }

    # 8. HHEM Hallucination Check (warm)
    hhem = HallucinationChecker()
    context_chunks = [r.get("text_content", "") for r in budgeted[:3]]
    fake_answer = "The company allows remote work up to 3 days per week."

    # Warm up HHEM model
    await hhem.check(fake_answer, context_chunks)

    start = time.monotonic()
    hall_result = await hhem.check(fake_answer, context_chunks)
    hhem_latency = (time.monotonic() - start) * 1000
    baselines["hhem_hallucination_check"] = {
        "latency_ms": round(hhem_latency, 2),
        "score": hall_result.get("score"),
        "passed": hall_result.get("passed"),
        "num_chunks": len(context_chunks),
    }

    await client.close()

    # Print summary
    print("\n=== Latency Baselines ===\n")
    total = 0.0
    for stage, data in baselines.items():
        lat = data["latency_ms"]
        total += lat
        print(f"  {stage:30s}  {lat:8.2f} ms")
    print(f"  {'TOTAL (without LLM)':30s}  {total:8.2f} ms")
    print()

    return baselines


if __name__ == "__main__":
    baselines = asyncio.run(capture_baselines())
    # Also write to JSON for docs
    print(json.dumps(baselines, indent=2))
