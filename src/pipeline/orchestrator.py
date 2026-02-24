from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from src.models.schemas import QueryMetadata, QueryRequest, QueryResponse, SourceInfo
from src.observability.logging import bind_trace_context, clear_trace_context

if TYPE_CHECKING:
    from src.observability.tracing import TracingService
    from src.pipeline.chunking.chunker import DocumentChunker
    from src.pipeline.chunking.metadata_extractor import MetadataExtractor
    from src.pipeline.compression.bm25_compressor import BM25Compressor
    from src.pipeline.compression.token_budget import TokenBudgetEnforcer
    from src.pipeline.generation.llm_client import LLMClient
    from src.pipeline.quality import HallucinationChecker
    from src.pipeline.reranking.cohere_reranker import CohereReranker
    from src.pipeline.retrieval.deduplication import Deduplicator
    from src.pipeline.retrieval.embeddings import EmbeddingService
    from src.pipeline.retrieval.query_expander import QueryExpander
    from src.pipeline.retrieval.vector_store import VectorStore
    from src.pipeline.routing import QueryRouter
    from src.pipeline.safety import SafetyChecker

logger = structlog.get_logger()


class PipelineOrchestrator:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        deduplicator: Deduplicator,
        reranker: CohereReranker,
        bm25_compressor: BM25Compressor,
        token_budget: TokenBudgetEnforcer,
        llm_client: LLMClient,
        safety_checker: SafetyChecker,
        query_router: QueryRouter,
        hallucination_checker: HallucinationChecker,
        tracing: TracingService,
        chunker: DocumentChunker,
        metadata_extractor: MetadataExtractor,
        query_expander: QueryExpander | None = None,
    ) -> None:
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._deduplicator = deduplicator
        self._reranker = reranker
        self._bm25 = bm25_compressor
        self._token_budget = token_budget
        self._llm = llm_client
        self._safety = safety_checker
        self._router = query_router
        self._hallucination = hallucination_checker
        self._tracing = tracing
        self._chunker = chunker
        self._metadata_extractor = metadata_extractor
        self._query_expander = query_expander

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Execute the full RAG pipeline for a query."""
        start_time = time.monotonic()

        trace = self._tracing.create_trace(
            name="pipeline_query",
            user_id=request.user_id,
            session_id=request.session_id,
            metadata={"tenant_id": request.tenant_id},
        )

        # Bind trace context for structured logging
        bind_trace_context(trace_id=trace.trace_id, user_id=request.user_id)
        logger.info("pipeline.request.received", query=request.query[:200], user_id=request.user_id)

        # 1. Safety check
        with trace.span("input_safety") as span:
            safety_result = await self._safety.check_input(request.query, request.user_id)
            span.set_attribute("passed", safety_result["passed"])
            span.set_attribute("skipped", safety_result.get("skipped", False))

            safety_latency = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "pipeline.safety.checked",
                passed=safety_result["passed"],
                blocked_reason=safety_result.get("reason"),
                latency_ms=safety_latency,
            )

            if not safety_result["passed"]:
                clear_trace_context()
                return QueryResponse(
                    answer=None,
                    trace_id=trace.trace_id,
                    metadata=QueryMetadata(
                        route_used="blocked",
                        model="none",
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        tokens_used=0,
                    ),
                    message=f"Input blocked: {safety_result.get('reason', 'safety check failed')}",
                )

        # 2. Query routing (stub)
        with trace.span("query_routing") as span:
            route_result = await self._router.route(request.query)
            span.set_attribute("route", route_result["route"])
            span.set_attribute("skipped", route_result.get("skipped", False))

        logger.info(
            "pipeline.routing.completed",
            route=route_result["route"],
            confidence=route_result.get("confidence"),
            latency_ms=int((time.monotonic() - start_time) * 1000),
        )

        # 3. Route-dependent dispatch
        route = route_result["route"]

        if route == "escalate_human":
            latency_ms = int((time.monotonic() - start_time) * 1000)
            self._tracing.flush()
            return QueryResponse(
                answer=None,
                trace_id=trace.trace_id,
                sources=[],
                metadata=QueryMetadata(
                    route_used=route,
                    model="none",
                    latency_ms=latency_ms,
                    tokens_used=0,
                ),
                fallback=True,
                message="This query has been routed to a human agent. A support representative will follow up shortly.",
            )

        if route == "sql_structured_data":
            raise NotImplementedError(
                f"Route '{route}' requires a Text-to-SQL handler (Wave 3+). "
                "Wire a SQL generation service into the orchestrator to support this route."
            )

        if route == "api_lookup":
            raise NotImplementedError(
                f"Route '{route}' requires an API lookup handler (Wave 3+). "
                "Wire an external API service into the orchestrator to support this route."
            )

        if route == "direct_llm":
            # Skip retrieval entirely — go straight to generation
            with trace.span("retrieval") as span:
                span.set_attribute("skipped", True)
                span.set_attribute("reason", "direct_llm route — no retrieval needed")
                reranked = []

            with trace.span("compression") as span:
                span.set_attribute("skipped", True)
                span.set_attribute("tokens_before", 0)
                span.set_attribute("tokens_after", 0)
                budgeted = []

            with trace.generation(
                name="generation",
                model=self._llm._model,
                input=request.query,
            ) as gen:
                llm_result = await self._llm.generate(
                    query=request.query,
                    context_chunks=[],
                    temperature=request.options.temperature,
                    max_tokens=request.options.max_tokens,
                )
                gen.set_output(
                    llm_result["answer"],
                    usage={
                        "input": llm_result["tokens_in"],
                        "output": llm_result["tokens_out"],
                    },
                )

            with trace.span("hallucination_check") as span:
                span.set_attribute("skipped", True)
                span.set_attribute("reason", "direct_llm route — no context to check against")
                hall_result = {"score": None, "passed": True, "skipped": True}

            latency_ms = int((time.monotonic() - start_time) * 1000)
            self._tracing.flush()

            return QueryResponse(
                answer=llm_result["answer"],
                trace_id=trace.trace_id,
                sources=[],
                metadata=QueryMetadata(
                    route_used=route,
                    faithfulness_score=None,
                    model=llm_result["model"],
                    latency_ms=latency_ms,
                    tokens_used=llm_result["tokens_in"] + llm_result["tokens_out"],
                ),
            )

        # route == "rag_knowledge_base" (default) — full retrieval path

        # 4. Retrieval (with optional multi-query expansion)
        with trace.span("retrieval") as span:
            if self._query_expander:
                from src.pipeline.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion

                queries = await self._query_expander.expand(request.query)
                span.set_attribute("expanded_queries", len(queries))

                all_result_lists: list[list[dict[str, Any]]] = []
                for q in queries:
                    q_embedding = await self._embedding.embed_query(q)
                    q_results = await self._vector_store.search(
                        query_embedding=q_embedding,
                        top_k=20,
                        tenant_id=request.tenant_id,
                    )
                    all_result_lists.append(q_results)

                raw_results = reciprocal_rank_fusion(all_result_lists)
            else:
                query_embedding = await self._embedding.embed_query(request.query)
                raw_results = await self._vector_store.search(
                    query_embedding=query_embedding,
                    top_k=20,
                    tenant_id=request.tenant_id,
                )

            span.set_attribute("num_results_raw", len(raw_results))

            # 4. Deduplication
            deduped = self._deduplicator.deduplicate(raw_results)
            span.set_attribute("num_results_after_dedup", len(deduped))

            # 5. Reranking
            reranked = await self._reranker.rerank(request.query, deduped)
            span.set_attribute("num_results_after_rerank", len(reranked))

        logger.info("pipeline.retrieval.completed", num_results=len(reranked), latency_ms=int((time.monotonic() - start_time) * 1000))

        # 6. Compression
        with trace.span("compression") as span:
            from src.utils.tokens import count_tokens

            tokens_before = sum(count_tokens(c.get("text_content", "")) for c in reranked)

            compressed = self._bm25.compress(request.query, reranked)
            budgeted = self._token_budget.enforce(compressed)

            tokens_after = sum(count_tokens(c.get("text_content", "")) for c in budgeted)

            span.set_attribute("tokens_before", tokens_before)
            span.set_attribute("tokens_after", tokens_after)
            span.set_attribute("compression_ratio", round(tokens_after / max(tokens_before, 1), 2))
            span.set_attribute("method", "bm25_subscoring")

        logger.info(
            "pipeline.compression.completed",
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            ratio=round(tokens_after / max(tokens_before, 1), 2),
        )

        # 7. Generation
        with trace.generation(
            name="generation",
            model=self._llm._model,
            input=request.query,
        ) as gen:
            llm_result = await self._llm.generate(
                query=request.query,
                context_chunks=budgeted,
                temperature=request.options.temperature,
                max_tokens=request.options.max_tokens,
            )
            gen.set_output(
                llm_result["answer"],
                usage={
                    "input": llm_result["tokens_in"],
                    "output": llm_result["tokens_out"],
                },
            )

        logger.info(
            "pipeline.generation.completed",
            model=llm_result["model"],
            tokens_in=llm_result["tokens_in"],
            tokens_out=llm_result["tokens_out"],
            latency_ms=int((time.monotonic() - start_time) * 1000),
        )

        # 8. Hallucination check (HHEM)
        with trace.span("hallucination_check") as span:
            context_chunks = [c.get("text_content", "") for c in budgeted]
            hall_result = await self._hallucination.check(llm_result["answer"], context_chunks)
            span.set_attribute("score", hall_result["score"])
            span.set_attribute("passed", hall_result["passed"])
            span.set_attribute("level", hall_result.get("level", "unknown"))
            span.set_attribute("model", hall_result.get("model", "unknown"))
            span.set_attribute("latency_ms", hall_result.get("latency_ms", 0))
            span.set_attribute("skipped", False)

        logger.info(
            "pipeline.hallucination.checked",
            score=hall_result["score"],
            level=hall_result.get("level"),
            latency_ms=hall_result.get("latency_ms"),
        )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Build sources
        sources = [
            SourceInfo(
                doc_id=r.get("metadata", {}).get("doc_id", "unknown"),
                chunk_id=r.get("metadata", {}).get("chunk_id", r.get("id", "unknown")),
                text_snippet=r.get("text_content", "")[:200],
                relevance_score=r.get("relevance_score", r.get("score", 0.0)),
                source_url=r.get("metadata", {}).get("source_url"),
            )
            for r in reranked
        ]

        # Set trace-level scores and save
        trace.set_score("faithfulness", hall_result["score"])
        trace.save_local()
        self._tracing.flush()

        # Handle hallucination check result
        hall_level = hall_result.get("level", "pass")

        if hall_level == "fail":
            logger.info("pipeline.request.completed", total_latency_ms=latency_ms, fallback=True)
            clear_trace_context()
            return QueryResponse(
                answer=None,
                trace_id=trace.trace_id,
                sources=sources if request.options.include_sources else [],
                metadata=QueryMetadata(
                    route_used=route_result["route"],
                    faithfulness_score=hall_result["score"],
                    model=llm_result["model"],
                    latency_ms=latency_ms,
                    tokens_used=llm_result["tokens_in"] + llm_result["tokens_out"],
                ),
                fallback=True,
                message=(
                    "I found relevant information but I'm not confident in my answer. "
                    "Here are the source documents for your reference."
                ),
            )

        disclaimer = None
        if hall_level == "warn":
            disclaimer = (
                "Note: This response may not be fully supported by the retrieved documents. "
                "Please verify critical details against the source materials."
            )

        logger.info("pipeline.request.completed", total_latency_ms=latency_ms, fallback=False)
        clear_trace_context()

        return QueryResponse(
            answer=llm_result["answer"],
            trace_id=trace.trace_id,
            sources=sources if request.options.include_sources else [],
            metadata=QueryMetadata(
                route_used=route_result["route"],
                faithfulness_score=hall_result["score"],
                model=llm_result["model"],
                latency_ms=latency_ms,
                tokens_used=llm_result["tokens_in"] + llm_result["tokens_out"],
            ),
            message=disclaimer,
        )

    async def ingest_file(
        self,
        file_path: str,
        user_id: str,
        tenant_id: str,
        doc_type: str = "markdown",
        source_url: str | None = None,
        access_level: str = "internal",
    ) -> dict[str, Any]:
        """Ingest a document file into the vector store."""
        doc_id = str(uuid4())

        trace = self._tracing.create_trace(
            name="pipeline_ingest",
            user_id=user_id,
            metadata={"tenant_id": tenant_id, "doc_id": doc_id},
        )

        with trace.span("chunking") as span:
            chunks = self._chunker.chunk_file(file_path)
            span.set_attribute("num_chunks", len(chunks))

        with trace.span("embedding") as span:
            texts = [c["text_content"] for c in chunks]
            embeddings = await self._embedding.embed_texts(texts)
            span.set_attribute("num_embeddings", len(embeddings))

        with trace.span("upsert") as span:
            points = []
            for chunk, embedding in zip(chunks, embeddings, strict=False):
                meta = self._metadata_extractor.create_metadata(
                    chunk=chunk,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    doc_id=doc_id,
                    doc_type=doc_type,
                    source_url=source_url,
                    access_level=access_level,
                )
                points.append({
                    "vector_id": meta.chunk_id,
                    "embedding": embedding,
                    "text_content": chunk["text_content"],
                    "metadata": meta.model_dump(mode="json"),
                })

            await self._vector_store.upsert_batch(points)
            span.set_attribute("points_upserted", len(points))

        self._tracing.flush()

        return {
            "doc_id": doc_id,
            "chunks_created": len(chunks),
            "status": "success",
        }
