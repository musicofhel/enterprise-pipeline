#!/usr/bin/env python3
"""Validate environment variables and service connectivity.

Usage:
    python scripts/validate_environment.py
    python scripts/validate_environment.py --strict
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

SYMBOLS = {PASS: "\u2713", FAIL: "\u2717", SKIP: "\u26a0"}


class CheckResult:
    def __init__(self, name: str, status: str, details: str, fix: str = "") -> None:
        self.name = name
        self.status = status
        self.details = details
        self.fix = fix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    """Show first 8 and last 3 chars of a secret."""
    if len(value) <= 14:
        return value[:4] + "..." + value[-3:]
    return value[:8] + "..." + value[-3:]


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_env_var(key: str, *, required: bool) -> CheckResult:
    value = _get(key)
    if value:
        return CheckResult(key, PASS, _mask(value))
    label = "required" if required else "recommended"
    status = FAIL if required else SKIP
    fix = f"Set {key} in .env" if required else ""
    return CheckResult(key, status, f"Not set ({label})", fix)


async def check_qdrant_connection() -> CheckResult:
    host = _get("QDRANT_HOST", "localhost")
    port = _get("QDRANT_PORT", "6333")
    url = f"http://{host}:{port}/collections"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return CheckResult("Qdrant connection", PASS, f"{host}:{port}")
    except Exception as exc:
        return CheckResult(
            "Qdrant connection",
            FAIL,
            str(exc)[:60],
            f"Start Qdrant: docker run -p {port}:6333 qdrant/qdrant",
        )


async def check_qdrant_collection() -> CheckResult:
    host = _get("QDRANT_HOST", "localhost")
    port = _get("QDRANT_PORT", "6333")
    url = f"http://{host}:{port}/collections/documents"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return CheckResult(
                    "Qdrant collection",
                    FAIL,
                    '"documents" collection not found',
                    "Run: python scripts/ingest_documents.py or create collection manually",
                )
            resp.raise_for_status()
            data = resp.json()
            dim = data.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            size = dim["size"] if isinstance(dim, dict) and "size" in dim else "unknown"
            detail = f'"documents" ({size} dim)'
            if size != 384 and size != "unknown":
                detail += " (expected 384)"
            return CheckResult("Qdrant collection", PASS, detail)
    except httpx.HTTPStatusError as exc:
        return CheckResult("Qdrant collection", FAIL, str(exc)[:60])
    except Exception:
        return CheckResult("Qdrant collection", SKIP, "Qdrant not reachable")


async def check_openrouter() -> CheckResult:
    key = _get("OPENROUTER_API_KEY")
    if not key:
        return CheckResult("OpenRouter API", FAIL, "No API key", "Set OPENROUTER_API_KEY in .env")
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        resp = await client.chat.completions.create(
            model="anthropic/claude-haiku-4-5",
            messages=[{"role": "user", "content": "Say ok"}],
            max_tokens=5,
        )
        text = (resp.choices[0].message.content or "").strip()
        return CheckResult("OpenRouter API", PASS, f'Response: "{text[:30]}"')
    except Exception as exc:
        return CheckResult(
            "OpenRouter API",
            FAIL,
            str(exc)[:60],
            "Check OPENROUTER_API_KEY is valid and has credits",
        )


async def check_cohere() -> CheckResult:
    key = _get("COHERE_API_KEY")
    if not key:
        return CheckResult("Cohere API", SKIP, "No API key")
    try:
        import cohere

        client = cohere.Client(key)
        result = client.rerank(
            model="rerank-english-v3.0",
            query="test",
            documents=["test doc"],
            top_n=1,
        )
        if result.results:
            return CheckResult("Cohere API", PASS, "Rerank OK")
        return CheckResult("Cohere API", FAIL, "Empty rerank response")
    except Exception as exc:
        return CheckResult(
            "Cohere API", FAIL, str(exc)[:60], "Check COHERE_API_KEY is valid"
        )


async def check_lakera() -> CheckResult:
    key = _get("LAKERA_API_KEY")
    if not key:
        return CheckResult("Lakera Guard API", SKIP, "No API key")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.lakera.ai/v2/guard",
                json={"input": "test input"},
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            return CheckResult("Lakera Guard API", PASS, "Guard responded")
    except Exception as exc:
        return CheckResult(
            "Lakera Guard API", FAIL, str(exc)[:60], "Check LAKERA_API_KEY is valid"
        )


async def check_langfuse() -> CheckResult:
    pub = _get("LANGFUSE_PUBLIC_KEY")
    sec = _get("LANGFUSE_SECRET_KEY")
    host = _get("LANGFUSE_HOST", "http://localhost:3100")
    if not pub or not sec:
        return CheckResult("Langfuse", SKIP, "No keys configured")
    try:
        from langfuse import Langfuse

        lf = Langfuse(public_key=pub, secret_key=sec, host=host)
        lf.auth_check()
        lf.shutdown()
        return CheckResult("Langfuse", PASS, f"Connected to {host}")
    except Exception as exc:
        lf_err = str(exc)[:60]
        return CheckResult(
            "Langfuse", FAIL, lf_err, f"Check Langfuse keys and host ({host})"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _capability_summary(results: list[CheckResult]) -> list[str]:
    """Summarize what the pipeline can/cannot do based on results."""
    lookup: dict[str, str] = {r.name: r.status for r in results}

    available: list[str] = []
    missing: list[str] = []

    if lookup.get("OPENROUTER_API_KEY") == PASS and lookup.get("OpenRouter API") == PASS:
        available.append("routing, generation")
    else:
        missing.append("LLM generation")

    if lookup.get("Qdrant connection") == PASS:
        available.append("retrieval")
    else:
        missing.append("retrieval")

    available.append("L1 safety, compression, HHEM")

    if lookup.get("COHERE_API_KEY") == PASS:
        available.append("reranking")
    else:
        missing.append("reranking (will use passthrough)")

    if lookup.get("LAKERA_API_KEY") == PASS:
        available.append("L2 safety")
    else:
        missing.append("L2 safety")

    if lookup.get("LANGFUSE_PUBLIC_KEY") == PASS:
        available.append("Langfuse tracing")
    else:
        missing.append("Langfuse (local fallback)")

    lines: list[str] = []
    if available:
        lines.append(f"  Pipeline can run with: {', '.join(available)}")
    if missing:
        lines.append(f"  Missing: {', '.join(missing)}")
    return lines


def _print_report(results: list[CheckResult]) -> None:
    col1 = max(len(r.name) for r in results)
    col2 = 10
    col3 = max(len(r.details) for r in results)

    # Ensure minimum widths
    col1 = max(col1, 24)
    col3 = max(col3, 21)
    total = col1 + col2 + col3 + 6  # 6 for separators and padding

    # Ensure footer lines fit (summary + capability lines)
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, SKIP, FAIL)}
    summary = f"Result: {counts[PASS]} PASS, {counts[SKIP]} SKIP, {counts[FAIL]} FAIL"
    cap_lines = _capability_summary(results)
    footer_lines = [summary, *cap_lines]
    max_footer = max((len(line) for line in footer_lines), default=0) + 2  # +2 for padding
    if max_footer > total:
        col3 += max_footer - total
        total = max_footer

    title = "Environment Validation Report"
    title_pad = (total - len(title)) // 2

    print(f"\u2554{'═' * total}\u2557")
    print(f"\u2551{' ' * title_pad}{title}{' ' * (total - title_pad - len(title))}\u2551")
    print(f"\u2560{'═' * (col1 + 2)}\u2564{'═' * col2}\u2564{'═' * (col3 + 2)}\u2563")
    print(
        f"\u2551 {'Check':<{col1}} \u2502{'Status':^{col2}}\u2502 {'Details':<{col3}} \u2551"
    )
    print(f"\u2560{'═' * (col1 + 2)}\u256a{'═' * col2}\u256a{'═' * (col3 + 2)}\u2563")

    for r in results:
        sym = SYMBOLS[r.status]
        status_str = f"{sym} {r.status}"
        print(
            f"\u2551 {r.name:<{col1}} \u2502{status_str:^{col2}}\u2502 {r.details:<{col3}} \u2551"
        )

    print(f"\u2560{'═' * (col1 + 2)}\u2567{'═' * col2}\u2567{'═' * (col3 + 2)}\u2563")
    print(f"\u2551 {summary:<{total - 2}} \u2551")
    for line in cap_lines:
        print(f"\u2551 {line:<{total - 2}} \u2551")
    print(f"\u255a{'═' * total}\u255d")

    # Print fix suggestions for failures
    failures = [r for r in results if r.status == FAIL and r.fix]
    if failures:
        print("\nHow to fix:")
        for r in failures:
            print(f"  {r.name}: {r.fix}")


async def run(strict: bool) -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    results: list[CheckResult] = []

    # 1. Env var checks
    env_checks = [
        ("OPENROUTER_API_KEY", True),
        ("COHERE_API_KEY", False),
        ("LAKERA_API_KEY", False),
        ("LANGFUSE_PUBLIC_KEY", False),
        ("LANGFUSE_SECRET_KEY", False),
        ("LANGFUSE_HOST", False),
        ("QDRANT_HOST", False),
        ("QDRANT_PORT", False),
    ]
    for key, required in env_checks:
        req = required or strict
        results.append(check_env_var(key, required=req))

    # 2. Service connectivity checks
    results.append(await check_qdrant_connection())
    results.append(await check_qdrant_collection())
    results.append(await check_openrouter())
    results.append(await check_cohere())
    results.append(await check_lakera())
    results.append(await check_langfuse())

    _print_report(results)

    has_failure = any(r.status == FAIL for r in results)
    return 1 if has_failure else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate pipeline environment")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat all recommended checks as required",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.strict)))


if __name__ == "__main__":
    main()
