from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class QueryRouter:
    """Stub query router — always returns the default route. Wave 2 will add Semantic Router."""

    def __init__(self, default_route: str = "rag_knowledge_base") -> None:
        self._default_route = default_route

    async def route(self, query: str) -> dict[str, Any]:
        logger.info("routing_stub", route=self._default_route)
        return {
            "route": self._default_route,
            "confidence": 1.0,
            "skipped": True,
        }
