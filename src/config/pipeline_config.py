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
    default_route: str = "rag_knowledge_base"
    confidence_threshold: float = 0.7


class QueryExpansionConfig(BaseModel):
    enabled: bool = True
    method: str = "multi_query"
    num_queries: int = 3


class InjectionDetectionConfig(BaseModel):
    layer_1: str = "guardrails_ai"
    layer_2: str = "lakera_guard"
    layer_3_enabled: bool = False


class SafetyConfig(BaseModel):
    injection_detection: InjectionDetectionConfig = Field(default_factory=InjectionDetectionConfig)
    pii_detection: bool = True
    pii_action: str = "redact"


class GenerationConfig(BaseModel):
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_output_tokens: int = 1000
    fallback_model: str = "claude-sonnet-4-5-20250929"


class HallucinationConfig(BaseModel):
    model: str = "vectara/hhem-2.1"
    threshold_pass: float = 0.85
    threshold_warn: float = 0.70
    fallback_on_fail: bool = True


class ObservabilityConfig(BaseModel):
    langfuse_enabled: bool = True
    langfuse_sample_rate: float = 1.0
    export_to_s3: bool = True
    export_schedule: str = "daily"


class ExperimentationConfig(BaseModel):
    shadow_mode_enabled: bool = False
    shadow_pipeline_version: str | None = None
    feature_flag_provider: str = "launchdarkly"


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
