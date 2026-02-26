"""Smart model tier routing — selects cheaper or more powerful models based on query signals.

No LLM call — all heuristics run in <5ms.
"""
from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.config.pipeline_config import ModelRoutingConfig

logger = structlog.get_logger()

# Keywords that suggest complex queries needing the standard/complex model
COMPLEX_KEYWORDS = re.compile(
    r"\b(compare|analyze|summarize all|across|evaluate|assess|contrast|"
    r"comprehensive|detailed analysis|multi-part|in-depth)\b",
    re.IGNORECASE,
)


class ModelTier(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    COMPLEX = "complex"


def determine_model_tier(
    query: str,
    route: str,
    context_tokens: int = 0,
) -> ModelTier:
    """Determine the model tier from query/route/context signals.

    Rules (evaluated in order):
    1. Route-based: direct_llm short queries → FAST
    2. Complexity heuristics: compare/analyze/etc. → COMPLEX
    3. Multiple questions (2+ ?) → COMPLEX
    4. Context size: <500 tokens → FAST, >2000 → COMPLEX
    5. Default → STANDARD
    """
    word_count = len(query.split())
    question_marks = query.count("?")

    # 1. Route-based shortcuts
    if route == "direct_llm" and word_count < 10:
        return ModelTier.FAST

    # 2. Complexity keywords
    if COMPLEX_KEYWORDS.search(query):
        return ModelTier.COMPLEX

    # 3. Multiple questions
    if question_marks >= 2:
        return ModelTier.COMPLEX

    # 4. Context size signals
    if context_tokens > 2000:
        return ModelTier.COMPLEX
    if context_tokens > 0 and context_tokens < 500 and word_count < 10:
        return ModelTier.FAST

    # 5. Default
    return ModelTier.STANDARD


def resolve_model(
    config: ModelRoutingConfig,
    query: str,
    route: str,
    context_tokens: int = 0,
) -> dict[str, Any]:
    """Resolve the model and max_output_tokens for a query.

    Returns dict with: model, max_output_tokens, tier
    """
    if not config.enabled:
        return {
            "model": None,  # Use LLMClient default
            "max_output_tokens": None,
            "tier": "default",
        }

    if config.force_model:
        return {
            "model": config.force_model,
            "max_output_tokens": None,
            "tier": "forced",
        }

    tier = determine_model_tier(query, route, context_tokens)
    tier_config = config.tiers.get(tier.value)

    if not tier_config:
        return {
            "model": None,
            "max_output_tokens": None,
            "tier": tier.value,
        }

    logger.info(
        "model_tier_resolved",
        tier=tier.value,
        model=tier_config.model,
        max_output_tokens=tier_config.max_output_tokens,
        query_words=len(query.split()),
        context_tokens=context_tokens,
    )

    return {
        "model": tier_config.model,
        "max_output_tokens": tier_config.max_output_tokens,
        "tier": tier.value,
    }
