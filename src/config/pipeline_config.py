from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from deepmerge import always_merger
from pydantic import BaseModel, Field


class ChunkingConfig(BaseModel):
    strategy: str = "by_title"
    max_characters: int = 1500
    overlap: int = 200
    provider: str = "unstructured"


class RetrievalConfig(BaseModel):
    top_k: int = 20
    dedup_threshold: float = 0.95
    rerank_provider: str = "cohere"
    rerank_top_n: int = 5


class CompressionConfig(BaseModel):
    method: str = "bm25_subscoring"
    sentences_per_chunk: int = 5
    max_total_tokens: int = 4000


class RoutingConfig(BaseModel):
    provider: str = "semantic_router"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_provider: str = "local"
    default_route: str = "rag_knowledge_base"
    confidence_threshold: float = 0.5


class QueryExpansionConfig(BaseModel):
    enabled: bool = True
    method: str = "multi_query"
    num_queries: int = 3
    model: str = "anthropic/claude-haiku-4-5"
    mode: str = "conditional"  # "always" | "conditional" | "never"
    confidence_threshold: float = 0.75  # skip expansion when routing confidence >= this


class InjectionDetectionConfig(BaseModel):
    layer_1: str = "guardrails_ai"
    layer_2: str = "lakera_guard"
    layer_3_enabled: bool = False


class SafetyConfig(BaseModel):
    injection_detection: InjectionDetectionConfig = Field(default_factory=InjectionDetectionConfig)
    pii_detection: bool = True
    pii_action: str = "redact"


class ModelTierConfig(BaseModel):
    model: str
    max_output_tokens: int


class ModelRoutingConfig(BaseModel):
    enabled: bool = True
    tiers: dict[str, ModelTierConfig] = Field(default_factory=lambda: {
        "fast": ModelTierConfig(model="anthropic/claude-haiku-4-5", max_output_tokens=512),
        "standard": ModelTierConfig(model="anthropic/claude-sonnet-4-5", max_output_tokens=1024),
        "complex": ModelTierConfig(model="anthropic/claude-sonnet-4-5", max_output_tokens=2048),
    })
    force_model: str | None = None  # Override: force all traffic to one model


class GenerationConfig(BaseModel):
    provider: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "anthropic/claude-sonnet-4-5"
    temperature: float = 0.1
    max_output_tokens: int = 1000
    fallback_model: str = "anthropic/claude-haiku-4-5"
    model_routing: ModelRoutingConfig = Field(default_factory=ModelRoutingConfig)


class HallucinationConfig(BaseModel):
    model: str = "vectara/hallucination_evaluation_model"
    threshold_pass: float = 0.85
    threshold_warn: float = 0.70
    fallback_on_fail: bool = True
    aggregation_method: str = "max"  # "max", "mean", or "min"


class MonitoringConfig(BaseModel):
    prometheus_enabled: bool = True
    embedding_drift_threshold: float = 0.15
    retrieval_canary_window: int = 1000
    daily_eval_sample_size: int = 50
    daily_eval_lookback_hours: int = 24


class ObservabilityConfig(BaseModel):
    langfuse_enabled: bool = True
    langfuse_sample_rate: float = 1.0
    export_to_s3: bool = True
    export_schedule: str = "daily"
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)


class ShadowModeConfig(BaseModel):
    enabled: bool = False
    candidate_model: str | None = None
    candidate_prompt_path: str | None = None
    sample_rate: float = 0.1
    budget_limit_usd: float = 10.0
    circuit_breaker_latency_multiplier: float = 3.0


class FeatureFlagConfig(BaseModel):
    enabled: bool = False
    config_path: str = "experiment_configs/flags.yaml"
    default_variant: str = "control"


class ExperimentationConfig(BaseModel):
    shadow_mode: ShadowModeConfig = Field(default_factory=ShadowModeConfig)
    feature_flags: FeatureFlagConfig = Field(default_factory=FeatureFlagConfig)
    # Backward compat — old flat fields with defaults
    shadow_mode_enabled: bool = False
    shadow_pipeline_version: str | None = None
    feature_flag_provider: str = "launchdarkly"


class RetentionConfig(BaseModel):
    vectors_days: int = 365
    traces_days: int = 90
    audit_logs_days: int = 2555  # ~7 years
    feedback_days: int = 365


class ComplianceConfig(BaseModel):
    deletion_sla_hours: int = 72
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    audit_log_immutable: bool = True
    audit_log_path: str = "audit_logs/local"


class PipelineConfig(BaseModel):
    model_config = {"frozen": True}

    version: str = "1.0.0"
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    compression: CompressionConfig = Field(default_factory=CompressionConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    query_expansion: QueryExpansionConfig = Field(default_factory=QueryExpansionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    hallucination: HallucinationConfig = Field(default_factory=HallucinationConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    experimentation: ExperimentationConfig = Field(default_factory=ExperimentationConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)


def load_pipeline_config(
    config_path: str | Path = "pipeline_config.yaml",
    env: str = "development",
    environments_dir: str | Path = "environments",
) -> PipelineConfig:
    """Load pipeline config from YAML, merge environment overlay, validate."""
    config_path = Path(config_path)
    environments_dir = Path(environments_dir)

    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")

    with open(config_path) as f:
        base_config: dict[str, Any] = yaml.safe_load(f) or {}

    # Merge environment overlay if it exists
    env_path = environments_dir / f"{env}.yaml"
    if env_path.exists():
        with open(env_path) as f:
            env_config: dict[str, Any] = yaml.safe_load(f) or {}
        base_config = always_merger.merge(base_config, env_config)

    return PipelineConfig(**base_config)
