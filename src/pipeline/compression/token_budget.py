from __future__ import annotations

from typing import Any

import structlog

from src.utils.tokens import count_tokens

logger = structlog.get_logger()


class TokenBudgetEnforcer:
    def __init__(self, max_tokens: int = 4000, model: str = "anthropic/claude-sonnet-4-5") -> None:
        self._max_tokens = max_tokens
        self._model = model

    def enforce(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Trim chunks to fit within the token budget, preserving order."""
        total_tokens = 0
        result: list[dict[str, Any]] = []

        for chunk in chunks:
            text = chunk.get("text_content", "")
            chunk_tokens = count_tokens(text, model=self._model)

            if total_tokens + chunk_tokens > self._max_tokens:
                # Include partial chunk if there's room
                remaining = self._max_tokens - total_tokens
                if remaining > 50:  # Only include if meaningful
                    from src.utils.tokens import truncate_to_token_budget

                    truncated = truncate_to_token_budget(text, remaining, model=self._model)
                    result.append({**chunk, "text_content": truncated, "truncated": True})
                    total_tokens += remaining
                break

            result.append(chunk)
            total_tokens += chunk_tokens

        logger.info(
            "token_budget_enforced",
            input_chunks=len(chunks),
            output_chunks=len(result),
            total_tokens=total_tokens,
            budget=self._max_tokens,
        )
        return result
