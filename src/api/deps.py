from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cohere
from langfuse import Langfuse
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from src.config.pipeline_config import PipelineConfig, load_pipeline_config
from src.config.settings import Settings
from src.experimentation.feature_flags import FeatureFlagService
from src.experimentation.shadow_mode import ShadowRunner
from src.observability.audit_log import AuditLogService
from src.observability.retrieval_canary import RetrievalQualityCanary
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
from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
from src.pipeline.retrieval.query_expander import QueryExpander
from src.pipeline.retrieval.vector_store import VectorStore
from src.pipeline.routing import QueryRouter
from src.pipeline.safety import SafetyChecker
from src.pipeline.safety.injection_detector import InjectionDetector
from src.pipeline.safety.lakera_guard import LakeraGuardClient
from src.pipeline.safety.pii_detector import PIIDetector
from src.services.deletion_service import DeletionService
from src.services.feedback_service import FeedbackService


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
        return TracingService(client=None, local_fallback=True)

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    return TracingService(client=client, local_fallback=True)


def get_audit_log_service() -> AuditLogService:
    config = get_pipeline_config()
    storage_dir = Path(config.compliance.audit_log_path)
    return AuditLogService(storage_dir=storage_dir)


def get_feedback_service() -> FeedbackService:
    audit_log = get_audit_log_service()
    return FeedbackService(audit_log=audit_log)


def get_deletion_service() -> DeletionService:
    settings = get_settings()

    qdrant_client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key.get_secret_value() or None,
    )
    vector_store = VectorStore(client=qdrant_client)
    audit_log = get_audit_log_service()
    tracing = get_tracing_service()
    feedback_service = get_feedback_service()
    return DeletionService(
        vector_store=vector_store,
        audit_log=audit_log,
        tracing=tracing,
        feedback_service=feedback_service,
    )


def get_feature_flag_service() -> FeatureFlagService | None:
    config = get_pipeline_config()
    ff_config = config.experimentation.feature_flags
    if not ff_config.enabled:
        return None
    audit_log = get_audit_log_service()
    return FeatureFlagService(config=ff_config, audit_log=audit_log)


def get_shadow_runner(llm_client: LLMClient | None = None) -> ShadowRunner | None:
    config = get_pipeline_config()
    shadow_config = config.experimentation.shadow_mode
    if not shadow_config.enabled:
        return None
    if llm_client is None:
        return None
    tracing = get_tracing_service()
    audit_log = get_audit_log_service()
    return ShadowRunner(
        llm_client=llm_client,
        tracing=tracing,
        config=shadow_config,
        audit_log=audit_log,
    )


def get_orchestrator() -> PipelineOrchestrator:
    settings = get_settings()
    config = get_pipeline_config()

    # LLM client — OpenRouter (OpenAI-compatible API)
    openrouter_client = AsyncOpenAI(
        base_url=config.generation.base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
    )
    qdrant_client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key.get_secret_value() or None,
    )
    cohere_client = cohere.AsyncClientV2(api_key=settings.cohere_api_key.get_secret_value())

    # Retrieval embeddings — via OpenRouter (text-embedding-3-small is available)
    embedding_service = EmbeddingService(
        client=openrouter_client,
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
        client=openrouter_client,
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

    # Routing embeddings — local sentence-transformers (no API key needed)
    local_embeddings = LocalEmbeddingService(model_name=config.routing.embedding_model)

    # Query expansion — uses OpenRouter with a cheaper model
    query_expander = QueryExpander(
        client=openrouter_client,
        num_queries=config.query_expansion.num_queries,
        model=config.query_expansion.model,
    ) if config.query_expansion.enabled else None

    # Experimentation
    feature_flags = get_feature_flag_service()
    shadow_runner = get_shadow_runner(llm_client=llm_client)

    # Observability
    retrieval_canary = RetrievalQualityCanary()

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
            embed_fn=local_embeddings.embed_texts,
        ),
        hallucination_checker=HallucinationChecker(
            model_name=config.hallucination.model,
            threshold_pass=config.hallucination.threshold_pass,
            threshold_warn=config.hallucination.threshold_warn,
            aggregation_method=config.hallucination.aggregation_method,
        ),
        tracing=tracing,
        chunker=chunker,
        metadata_extractor=metadata_extractor,
        query_expander=query_expander,
        feature_flags=feature_flags,
        shadow_runner=shadow_runner,
        retrieval_canary=retrieval_canary,
    )
