"""E2E pipeline trace for Wave 3 verification.

Runs the full pipeline with real local components:
- L1 injection detection (real regex)
- PII detection (real regex)
- Routing (real cosine sim with deterministic embeddings)
- Qdrant retrieval (mocked — requires live server)
- Cohere reranking (mocked — requires API key)
- Deduplication (real numpy cosine sim)
- BM25 compression (real spaCy + rank-bm25)
- Token budget (real tiktoken)
- LLM generation (mocked — requires API key)
- HHEM hallucination check (REAL model inference)
- Langfuse tracing (local JSON fallback — REAL file output)
- Structured logging (REAL JSON output)

Usage: python -m scripts.run_e2e_trace
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.schemas import QueryRequest
from src.observability.logging import setup_logging
from src.observability.tracing import LOCAL_TRACE_DIR, TracingService
from src.pipeline.chunking.chunker import DocumentChunker
from src.pipeline.chunking.metadata_extractor import MetadataExtractor
from src.pipeline.compression.bm25_compressor import BM25Compressor
from src.pipeline.compression.token_budget import TokenBudgetEnforcer
from src.pipeline.generation.llm_client import LLMClient
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.quality import HallucinationChecker
from src.pipeline.reranking.cohere_reranker import CohereReranker
from src.pipeline.retrieval.deduplication import Deduplicator
from src.pipeline.retrieval.embeddings import EmbeddingService
from src.pipeline.retrieval.vector_store import VectorStore
from src.pipeline.routing import QueryRouter
from src.pipeline.safety import SafetyChecker
from src.pipeline.safety.injection_detector import InjectionDetector
from src.pipeline.safety.pii_detector import PIIDetector


def build_orchestrator() -> PipelineOrchestrator:
    """Build orchestrator with mocked external deps, real local components."""

    # Mock OpenRouter client for embeddings + LLM (OpenAI-compatible API)
    openrouter_client = AsyncMock()
    embedding_response = MagicMock()
    embedding_item = MagicMock()
    embedding_item.embedding = [0.1] * 1536
    embedding_response.data = [embedding_item]
    openrouter_client.embeddings.create.return_value = embedding_response

    # Mock LLM response — realistic answer about remote work
    chat_response = MagicMock()
    choice = MagicMock()
    choice.message.content = (
        "The company's remote work policy for international employees allows up to 3 days "
        "per week of remote work, subject to manager approval and compliance with local "
        "labor laws. International employees must maintain a secure VPN connection and "
        "adhere to data residency requirements specific to their jurisdiction."
    )
    chat_response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 2400
    usage.completion_tokens = 280
    chat_response.usage = usage
    openrouter_client.chat.completions.create.return_value = chat_response

    # Mock Qdrant — return realistic chunks about remote work policy
    qdrant_client = AsyncMock()
    collections = MagicMock()
    collections.collections = []
    qdrant_client.get_collections.return_value = collections

    search_result = MagicMock()
    chunk_texts = [
        "Section 4.2: Remote Work Policy. All employees, including international team members, "
        "may work remotely up to 3 days per week with prior manager approval. Remote work "
        "arrangements must comply with the employee's local labor laws and regulations.",
        "Section 4.3: International Employee Requirements. International employees working "
        "remotely must maintain a company-approved VPN connection at all times. Data residency "
        "requirements vary by jurisdiction and must be followed per the compliance handbook.",
        "Section 4.4: Equipment and Connectivity. The company provides a monthly stipend of "
        "$150 for internet connectivity for approved remote workers. International employees "
        "may request additional equipment through the IT portal.",
        "Section 5.1: Performance Reviews. All employees, whether on-site or remote, are "
        "evaluated quarterly using the same performance framework. Remote work status does "
        "not affect promotion eligibility.",
        "Section 1.1: Company Overview. Founded in 2019, the company operates across 14 "
        "countries with over 2,000 employees. Our mission is to deliver enterprise AI "
        "solutions that transform how businesses operate.",
    ]
    points = []
    for i, text in enumerate(chunk_texts):
        point = MagicMock()
        point.id = f"point-{i}"
        point.score = 0.92 - (i * 0.04)
        point.payload = {
            "text_content": text,
            "doc_id": "hr-policy-v3",
            "chunk_id": f"hr-policy-v3-chunk-{40 + i}",
            "user_id": "test-user",
            "tenant_id": "test-tenant",
        }
        points.append(point)
    search_result.points = points
    qdrant_client.query_points.return_value = search_result

    # Mock Cohere reranker — return top 3 as reranked
    cohere_client = AsyncMock()
    rerank_response = MagicMock()
    rerank_results = []
    for i in range(3):
        item = MagicMock()
        item.index = i
        item.relevance_score = 0.95 - (i * 0.05)
        rerank_results.append(item)
    rerank_response.results = rerank_results
    cohere_client.rerank.return_value = rerank_response

    # Real local components
    embedding_service = EmbeddingService(client=openrouter_client, model="text-embedding-3-small")
    vector_store = VectorStore(client=qdrant_client)
    deduplicator = Deduplicator(threshold=0.95)
    reranker = CohereReranker(client=cohere_client, top_n=3)
    bm25_compressor = BM25Compressor(sentences_per_chunk=5)
    token_budget = TokenBudgetEnforcer(max_tokens=3000, model="anthropic/claude-sonnet-4-5")
    llm_client = LLMClient(
        client=openrouter_client, model="anthropic/claude-sonnet-4-5", temperature=0.1, max_output_tokens=1024
    )
    tracing = TracingService(client=None, local_fallback=True)
    chunker = DocumentChunker(strategy="by_title", max_characters=500, overlap=50)
    metadata_extractor = MetadataExtractor(embedding_model="text-embedding-3-small")
    safety_checker = SafetyChecker(
        injection_detector=InjectionDetector(),
        lakera_client=None,
        pii_detector=PIIDetector(),
    )
    query_router = QueryRouter(
        default_route="rag_knowledge_base",
        confidence_threshold=0.6,
        embedding_service=embedding_service,
    )
    hallucination_checker = HallucinationChecker(
        model_name="vectara/hallucination_evaluation_model",
        threshold_pass=0.85,
        threshold_warn=0.70,
        aggregation_method="max",
    )

    return PipelineOrchestrator(
        embedding_service=embedding_service,
        vector_store=vector_store,
        deduplicator=deduplicator,
        reranker=reranker,
        bm25_compressor=bm25_compressor,
        token_budget=token_budget,
        llm_client=llm_client,
        safety_checker=safety_checker,
        query_router=query_router,
        hallucination_checker=hallucination_checker,
        tracing=tracing,
        chunker=chunker,
        metadata_extractor=metadata_extractor,
    )


async def main() -> None:
    setup_logging(log_level="DEBUG", log_format="json", pipeline_version="wave-3-e2e")

    print("\n" + "=" * 80)
    print("WAVE 3 E2E PIPELINE TRACE")
    print("Query: What is the company's policy on remote work for international employees?")
    print("=" * 80 + "\n")

    orchestrator = build_orchestrator()

    request = QueryRequest(
        query="What is the company's policy on remote work for international employees?",
        user_id="e2e-test-user",
        tenant_id="e2e-test-tenant",
        session_id="e2e-session-001",
    )

    response = await orchestrator.query(request)

    print("\n" + "=" * 80)
    print("PIPELINE RESPONSE")
    print("=" * 80)
    print(f"  trace_id:           {response.trace_id}")
    print(f"  answer:             {response.answer[:120]}..." if response.answer and len(response.answer) > 120 else f"  answer:             {response.answer}")
    print(f"  route_used:         {response.metadata.route_used}")
    print(f"  faithfulness_score: {response.metadata.faithfulness_score}")
    print(f"  model:              {response.metadata.model}")
    print(f"  latency_ms:         {response.metadata.latency_ms}")
    print(f"  tokens_used:        {response.metadata.tokens_used}")
    print(f"  sources:            {len(response.sources)} source(s)")
    print(f"  fallback:           {response.fallback}")
    print(f"  message:            {response.message}")

    # Check for local trace file
    print("\n" + "=" * 80)
    print("LOCAL TRACE FILE")
    print("=" * 80)

    trace_files = list(LOCAL_TRACE_DIR.glob("*.json")) if LOCAL_TRACE_DIR.exists() else []
    if trace_files:
        # Find the most recent trace file
        latest = max(trace_files, key=lambda p: p.stat().st_mtime)
        data = json.loads(latest.read_text())
        print(f"  Path: {latest}")
        print(f"  trace_id:        {data['trace_id']}")
        print(f"  pipeline_version: {data['pipeline_version']}")
        print(f"  config_hash:     {data['config_hash'][:16]}...")
        print(f"  feature_flags:   {data['feature_flags']}")
        print(f"  total_latency_ms: {data['total_latency_ms']}")
        print(f"  scores:          {data['scores']}")
        print(f"\n  SPANS ({len(data['spans'])} total):")
        for i, span in enumerate(data["spans"], 1):
            attrs = span.get("attributes", {})
            skipped = attrs.get("skipped", False)
            status = "SKIPPED" if skipped else "REAL"
            print(f"    {i:2d}. {span['name']:<25s} [{status}] duration={span['duration_ms']:.1f}ms")
            for k, v in attrs.items():
                if k not in ("output",):  # Skip verbose output
                    print(f"        {k}: {v}")

        # Validate schema
        print("\n" + "=" * 80)
        print("SCHEMA VALIDATION")
        print("=" * 80)
        required_fields = [
            "trace_id", "timestamp", "user_id", "session_id",
            "pipeline_version", "config_hash", "feature_flags",
            "spans", "scores", "total_latency_ms", "total_cost_usd",
        ]
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"  FAIL: Missing fields: {missing}")
        else:
            print("  PASS: All required top-level fields present")

        required_spans = [
            "input_safety", "query_routing", "retrieval",
            "compression", "generation", "hallucination_check",
        ]
        span_names = {s["name"] for s in data["spans"]}
        missing_spans = [s for s in required_spans if s not in span_names]
        if missing_spans:
            print(f"  FAIL: Missing spans: {missing_spans}")
        else:
            print(f"  PASS: All {len(required_spans)} required spans present")

        # Check timing on all spans
        timing_ok = True
        for span in data["spans"]:
            if "start_time" not in span or "end_time" not in span or "duration_ms" not in span:
                print(f"  FAIL: Span '{span['name']}' missing timing fields")
                timing_ok = False
        if timing_ok:
            print("  PASS: All spans have start_time, end_time, duration_ms")

        # Check scores
        if data["scores"].get("faithfulness") is not None:
            print(f"  PASS: faithfulness score = {data['scores']['faithfulness']}")
        else:
            print("  FAIL: faithfulness score is None")
    else:
        print("  No trace files found!")

    print("\n" + "=" * 80)
    print("12-STAGE PIPELINE STATUS")
    print("=" * 80)
    stages = [
        ("1.  L1 Regex Injection Detection", "REAL", "Regex patterns on raw query"),
        ("2.  PII Detection (L1)", "REAL", "Regex patterns for SSN/email/phone/CC"),
        ("3.  Lakera Guard (L2)", "SKIPPED", "No LAKERA_API_KEY"),
        ("4.  Semantic Routing", "REAL", "Cosine sim (deterministic embeddings → default route)"),
        ("5.  Embedding", "MOCKED", "Requires OPENROUTER_API_KEY"),
        ("6.  Qdrant Retrieval", "MOCKED", "Requires live Qdrant server"),
        ("7.  Deduplication", "REAL", "numpy cosine sim on returned vectors"),
        ("8.  Cohere Reranking", "MOCKED", "Requires COHERE_API_KEY"),
        ("9.  BM25 Compression", "REAL", "spaCy + rank-bm25 sentence sub-scoring"),
        ("10. Token Budget", "REAL", "tiktoken enforcement to max_tokens"),
        ("11. LLM Generation", "MOCKED", "Requires OPENROUTER_API_KEY"),
        ("12. HHEM Hallucination Check", "REAL", "vectara/hallucination_evaluation_model on CPU"),
    ]
    for name, status, note in stages:
        marker = "X" if status == "REAL" else "~" if status == "SKIPPED" else " "
        print(f"  [{marker}] {name:<40s} {status:<8s} — {note}")

    real_count = sum(1 for _, s, _ in stages if s == "REAL")
    mocked_count = sum(1 for _, s, _ in stages if s == "MOCKED")
    skipped_count = sum(1 for _, s, _ in stages if s == "SKIPPED")
    print(f"\n  Summary: {real_count}/12 REAL, {mocked_count}/12 MOCKED, {skipped_count}/12 SKIPPED")
    print(f"  Wave 2 was: 6/12 REAL. Wave 3 adds HHEM → {real_count}/12 REAL.")


if __name__ == "__main__":
    asyncio.run(main())
