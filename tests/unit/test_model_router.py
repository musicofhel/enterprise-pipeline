"""Tests for smart model tier routing."""
from __future__ import annotations

import pytest

from src.config.pipeline_config import ModelRoutingConfig, ModelTierConfig
from src.pipeline.generation.model_router import ModelTier, determine_model_tier, resolve_model


class TestDetermineModelTier:
    """Tests for the tier determination heuristics."""

    def test_short_direct_llm_is_fast(self) -> None:
        tier = determine_model_tier("What is 2+2?", route="direct_llm")
        assert tier == ModelTier.FAST

    def test_long_direct_llm_is_standard(self) -> None:
        tier = determine_model_tier(
            "Write me a detailed professional email to decline a meeting invitation politely",
            route="direct_llm",
        )
        assert tier == ModelTier.STANDARD

    def test_compare_keyword_is_complex(self) -> None:
        tier = determine_model_tier(
            "Compare our data retention policies across all jurisdictions",
            route="rag_knowledge_base",
        )
        assert tier == ModelTier.COMPLEX

    def test_analyze_keyword_is_complex(self) -> None:
        tier = determine_model_tier(
            "Analyze the security policy for gaps",
            route="rag_knowledge_base",
        )
        assert tier == ModelTier.COMPLEX

    def test_multiple_questions_is_complex(self) -> None:
        tier = determine_model_tier(
            "What is our security policy? How does it compare to industry standards?",
            route="rag_knowledge_base",
        )
        assert tier == ModelTier.COMPLEX

    def test_large_context_is_complex(self) -> None:
        tier = determine_model_tier(
            "What is the refund policy?",
            route="rag_knowledge_base",
            context_tokens=3000,
        )
        assert tier == ModelTier.COMPLEX

    def test_small_context_short_query_is_fast(self) -> None:
        tier = determine_model_tier(
            "Refund policy?",
            route="rag_knowledge_base",
            context_tokens=200,
        )
        assert tier == ModelTier.FAST

    def test_normal_rag_query_is_standard(self) -> None:
        tier = determine_model_tier(
            "What is the company's remote work policy?",
            route="rag_knowledge_base",
        )
        assert tier == ModelTier.STANDARD

    def test_escalate_human_is_standard(self) -> None:
        tier = determine_model_tier(
            "I want to file a complaint",
            route="escalate_human",
        )
        assert tier == ModelTier.STANDARD


class TestResolveModel:
    """Tests for the full model resolution with config."""

    @pytest.fixture
    def config(self) -> ModelRoutingConfig:
        return ModelRoutingConfig(
            enabled=True,
            tiers={
                "fast": ModelTierConfig(model="anthropic/claude-haiku-4-5", max_output_tokens=512),
                "standard": ModelTierConfig(model="anthropic/claude-sonnet-4-5", max_output_tokens=1024),
                "complex": ModelTierConfig(model="anthropic/claude-sonnet-4-5", max_output_tokens=2048),
            },
        )

    def test_fast_tier_uses_haiku(self, config: ModelRoutingConfig) -> None:
        result = resolve_model(config, "Hi there", route="direct_llm")
        assert result["model"] == "anthropic/claude-haiku-4-5"
        assert result["max_output_tokens"] == 512
        assert result["tier"] == "fast"

    def test_standard_tier_uses_sonnet(self, config: ModelRoutingConfig) -> None:
        result = resolve_model(config, "What is the remote work policy?", route="rag_knowledge_base")
        assert result["model"] == "anthropic/claude-sonnet-4-5"
        assert result["max_output_tokens"] == 1024
        assert result["tier"] == "standard"

    def test_complex_tier_uses_sonnet_with_more_tokens(self, config: ModelRoutingConfig) -> None:
        result = resolve_model(
            config,
            "Compare our data retention policies across all jurisdictions",
            route="rag_knowledge_base",
        )
        assert result["model"] == "anthropic/claude-sonnet-4-5"
        assert result["max_output_tokens"] == 2048
        assert result["tier"] == "complex"

    def test_disabled_returns_none(self) -> None:
        config = ModelRoutingConfig(enabled=False)
        result = resolve_model(config, "test", route="rag_knowledge_base")
        assert result["model"] is None
        assert result["tier"] == "default"

    def test_force_model_overrides(self, config: ModelRoutingConfig) -> None:
        config = ModelRoutingConfig(
            enabled=True,
            force_model="anthropic/claude-sonnet-4-5",
            tiers=config.tiers,
        )
        result = resolve_model(config, "Hi there", route="direct_llm")
        assert result["model"] == "anthropic/claude-sonnet-4-5"
        assert result["tier"] == "forced"

    def test_tier_distribution_on_golden_dataset(self, config: ModelRoutingConfig) -> None:
        """Run the golden dataset queries and verify reasonable tier distribution."""
        queries = [
            ("What is the refund policy?", "rag_knowledge_base"),
            ("Hi", "direct_llm"),
            ("Write a haiku", "direct_llm"),
            ("Compare data retention across jurisdictions", "rag_knowledge_base"),
            ("What is 2+2?", "direct_llm"),
            ("Summarize the key points of our security policy", "rag_knowledge_base"),
            ("What are the pricing tiers?", "rag_knowledge_base"),
            ("Analyze the compliance gaps in our policy? What are the risks?", "rag_knowledge_base"),
        ]

        tiers: dict[str, int] = {}
        for query, route in queries:
            result = resolve_model(config, query, route)
            tier = result["tier"]
            tiers[tier] = tiers.get(tier, 0) + 1

        # Should have at least one of each tier (fast, standard, complex)
        assert "fast" in tiers, f"No fast tier queries, got: {tiers}"
        assert "standard" in tiers, f"No standard tier queries, got: {tiers}"
        assert "complex" in tiers, f"No complex tier queries, got: {tiers}"
