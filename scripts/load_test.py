"""Load test for the enterprise AI pipeline.

Uses httpx.AsyncClient with the FastAPI test client (no external server needed).
Sends queries from the golden dataset at configurable concurrency.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def load_queries(path: Path, count: int) -> list[str]:
    """Load queries from golden dataset JSONL, cycling if needed."""
    raw: list[str] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            q = entry.get("vars", {}).get("query", "")
            if q:
                raw.append(q)

    if not raw:
        print("ERROR: No queries found in golden dataset")
        sys.exit(1)

    return [raw[i % len(raw)] for i in range(count)]


async def send_query(
    client: Any,
    query: str,
    idx: int,
) -> dict:
    """Send a single query and return timing + result info."""
    payload = {
        "query": query,
        "user_id": f"load-test-user-{idx % 5}",
        "tenant_id": "load-test-tenant",
    }
    headers = {"X-API-Key": "sk-load-test"}
    start = time.monotonic()
    try:
        response = await client.post("/api/v1/query", json=payload, headers=headers)
        elapsed_ms = (time.monotonic() - start) * 1000
        body = response.json()
        blocked = body.get("message", "").startswith("Input blocked")
        error = response.status_code >= 400
        cost = 0.0
        if "metadata" in body:
            tokens = body["metadata"].get("tokens_used", 0)
            # Rough cost estimate for claude-sonnet-4-5 via OpenRouter
            # $3/M input, $15/M output -- approximate as $5/M blended
            cost = tokens * 5.0 / 1_000_000
        return {
            "idx": idx,
            "latency_ms": elapsed_ms,
            "status": response.status_code,
            "error": error,
            "blocked": blocked,
            "cost": cost,
            "query": query[:60],
        }
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "idx": idx,
            "latency_ms": elapsed_ms,
            "status": 0,
            "error": True,
            "blocked": False,
            "cost": 0.0,
            "query": query[:60],
            "exception": str(e),
        }


async def run_load_test(num_queries: int, concurrency: int) -> None:
    import httpx

    from src.api import auth as auth_mod
    from src.api.deps import get_pipeline_config, get_settings
    from src.main import create_app
    from src.models.rbac import Role

    # Inject test API key for RBAC
    auth_mod.API_KEY_ROLES["sk-load-test"] = Role.PIPELINE_WORKER

    # Clear lru_cache so app factory picks up current env
    get_settings.cache_clear()
    get_pipeline_config.cache_clear()

    app = create_app()
    golden_path = Path(__file__).parent.parent / "golden_dataset" / "promptfoo_tests.jsonl"
    queries = load_queries(golden_path, num_queries)

    # Determine test level label
    if num_queries <= 10 and concurrency <= 2:
        level = "Smoke"
    elif num_queries <= 50 and concurrency <= 5:
        level = "Light"
    elif num_queries <= 200 and concurrency <= 20:
        level = "Medium"
    else:
        level = "Heavy"

    print(f"\nStarting {level} load test: {num_queries} queries, concurrency {concurrency}")
    print(f"Golden dataset: {golden_path} ({len(set(queries))} unique queries)")
    print("=" * 60)

    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
        async def bounded_query(q: str, idx: int) -> dict:
            async with semaphore:
                return await send_query(client, q, idx)

        wall_start = time.monotonic()
        tasks = [bounded_query(q, i) for i, q in enumerate(queries)]
        results = await asyncio.gather(*tasks)
        wall_elapsed = time.monotonic() - wall_start

    # Compute stats
    latencies = [r["latency_ms"] for r in results]
    latencies_sorted = sorted(latencies)
    errors = sum(1 for r in results if r["error"])
    blocked = sum(1 for r in results if r["blocked"])
    total_cost = sum(r["cost"] for r in results)

    n = len(latencies_sorted)
    p50 = latencies_sorted[n // 2] if n else 0
    p95 = latencies_sorted[int(n * 0.95)] if n else 0
    p99 = latencies_sorted[int(n * 0.99)] if n else 0
    p_max = max(latencies_sorted) if n else 0
    p_min = min(latencies_sorted) if n else 0
    mean = statistics.mean(latencies) if n else 0

    throughput = num_queries / wall_elapsed if wall_elapsed > 0 else 0

    # Per-query detail
    print(f"\n{'#':<5} {'Query':<62} {'Status':<8} {'Latency':<12} {'Note':<10}")
    print("\u2500" * 100)
    for r in results:
        note = ""
        if r["error"]:
            note = "ERROR"
        elif r["blocked"]:
            note = "BLOCKED"
        print(
            f"{r['idx']:<5} "
            f"{r['query']:<62} "
            f"{r['status']:<8} "
            f"{r['latency_ms']:>8.0f} ms  "
            f"{note}"
        )

    # Aggregate
    print("\n\u2550\u2550\u2550 LOAD TEST RESULTS \u2550\u2550\u2550")
    print(f"Level:       {level} ({num_queries} queries, concurrency {concurrency})")
    print(f"Duration:    {wall_elapsed:.1f}s")
    print(f"Throughput:  {throughput:.2f} rps")
    print()
    print("Latency (ms):")
    print(f"  min:  {p_min:,.0f}")
    print(f"  p50:  {p50:,.0f}")
    print(f"  mean: {mean:,.0f}")
    print(f"  p95:  {p95:,.0f}")
    print(f"  p99:  {p99:,.0f}")
    print(f"  max:  {p_max:,.0f}")
    print()
    print(f"Errors:     {errors}/{num_queries} ({100*errors//num_queries}%)")
    print(f"Blocked:    {blocked}/{num_queries} ({100*blocked//num_queries}%)")
    print(f"Total cost: ${total_cost:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test the enterprise AI pipeline")
    parser.add_argument("--queries", type=int, default=10, help="Number of queries to send")
    parser.add_argument("--concurrency", type=int, default=1, help="Max concurrent requests")
    args = parser.parse_args()

    asyncio.run(run_load_test(args.queries, args.concurrency))


if __name__ == "__main__":
    main()
