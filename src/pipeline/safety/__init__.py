from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class SafetyChecker:
    """Stub safety checker — passes all inputs through. Wave 2 will add Lakera Guard + Guardrails AI."""

    async def check_input(self, text: str, user_id: str) -> dict[str, Any]:
        logger.info("safety_check_stub", action="passthrough", user_id=user_id)
        return {
            "passed": True,
            "reason": None,
            "skipped": True,
        }
