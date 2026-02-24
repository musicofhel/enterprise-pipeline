from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class HallucinationChecker:
    """Stub hallucination checker — passes all outputs. Wave 3 will add HHEM."""

    async def check(self, answer: str, context: str) -> dict[str, Any]:
        logger.info("hallucination_check_stub", action="passthrough")
        return {
            "passed": True,
            "score": 1.0,
            "skipped": True,
        }
