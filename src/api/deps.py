from __future__ import annotations

from functools import lru_cache

import cohere
from langfuse import Langfuse
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from src.config.pipeline_config import PipelineConfig, load_pipeline_config
from src.config.settings import Settings
from src.observability.tracing import TracingService
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
from src.pipeline.retrieval.query_expander import QueryExpander
from src.pipeline.retrieval.vector_store import VectorStore
from src.pipeline.routing import QueryRouter
from src.pipeline.safety import SafetyChecker
from src.pipeline.safety.injection_detector import InjectionDetector
from src.pipeline.safety.lakera_guard import LakeraGuardClient
from src.pipeline.safety.pii_detector import PIIDetector


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_pipeline_config() -> PipelineConfig:
    settings = get_settings()
    return load_pipeline_config(env=settings.pipeline_env)


def get_tracing_service() -> TracingService:
    settings = get_settings()
    config = get_pipeline_config()

    if not config.observability.langfuse_enabled or not settings.langfuse_public_key:
        return TracingService(client=None)

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    return TracingService(client=client)


def get_orchestrator() -> PipelineOrchestrator:
    settings = get_settings()
    config = get_pipeline_config()

    # External clients
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    qdrant_client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key.get_secret_value() or None,
    )
    cohere_client = cohere.AsyncClientV2(api_key=settings.cohere_api_key.get_secret_value())

    # Services
    embedding_service = EmbeddingService(
        client=openai_client,
        model=config.chunking.provider if config.chunking.provider != "unstructured" else "text-embedding-3-small",
    )
    vector_store = VectorStore(client=qdrant_client)
    deduplicator = Deduplicator(threshold=config.retrieval.dedup_threshold)
    reranker = CohereReranker(client=cohere_client, top_n=config.retrieval.rerank_top_n)
    bm25_compressor = BM25Compressor(sentences_per_chunk=config.compression.sentences_per_chunk)
    token_budget = TokenBudgetEnforcer(
        max_tokens=config.compression.max_total_tokens,
        model=config.generation.model,
    )
    llm_client = LLMClient(
        client=openai_client,
        model=config.generation.model,
        temperature=config.generation.temperature,
        max_output_tokens=config.generation.max_output_tokens,
    )
    tracing = get_tracing_service()
    chunker = DocumentChunker(
        strategy=config.chunking.strategy,
        max_characters=config.chunking.max_characters,
        overlap=config.chunking.overlap,
    )
    metadata_extractor = MetadataExtractor(embedding_model=embedding_service.model)

    # Safety layer — Lakera Guard wired when API key is available
    lakera_client = None
    lakera_key = settings.lakera_api_key.get_secret_value()
    if lakera_key:
        lakera_client = LakeraGuardClient(api_key=lakera_key)

    safety_checker = SafetyChecker(
        injection_detector=InjectionDetector(),
        lakera_client=lakera_client,
        pii_detector=PIIDetector(),
    )

    # Query expansion — uses the same OpenAI client
    query_expander = QueryExpander(
        client=openai_client,
        num_queries=config.query_expansion.num_queries,
        model=config.generation.model,
    ) if config.query_expansion.enabled else None

    return PipelineOrchestrator(
        embedding_service=embedding_service,
        vector_store=vector_store,
        deduplicator=deduplicator,
        reranker=reranker,
        bm25_compressor=bm25_compressor,
        token_budget=token_budget,
        llm_client=llm_client,
        safety_checker=safety_checker,
        query_router=QueryRouter(
            default_route=config.routing.default_route,
            confidence_threshold=config.routing.confidence_threshold,
            embedding_service=embedding_service,
        ),
        hallucination_checker=HallucinationChecker(),
        tracing=tracing,
        chunker=chunker,
        metadata_extractor=metadata_extractor,
        query_expander=query_expander,
    )
