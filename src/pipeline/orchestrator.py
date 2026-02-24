from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from src.models.schemas import QueryMetadata, QueryRequest, QueryResponse, SourceInfo

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

        # 1. Safety check (stub)
        with trace.span("input_safety") as span:
            safety_result = await self._safety.check_input(request.query, request.user_id)
            span.set_attribute("passed", safety_result["passed"])
            span.set_attribute("skipped", safety_result.get("skipped", False))

            if not safety_result["passed"]:
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

        # 3. Retrieval (with optional multi-query expansion)
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

        # 8. Hallucination check (stub)
        with trace.span("hallucination_check") as span:
            context_text = "\n".join(c.get("text_content", "") for c in budgeted)
            hall_result = await self._hallucination.check(llm_result["answer"], context_text)
            span.set_attribute("score", hall_result["score"])
            span.set_attribute("passed", hall_result["passed"])
            span.set_attribute("skipped", hall_result.get("skipped", False))

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

        self._tracing.flush()

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
