from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

LAKERA_API_URL = "https://api.lakera.ai/v2/guard"


class LakeraGuardClient:
    """Layer 2: ML-based injection detection via Lakera Guard API."""

    def __init__(self, api_key: str, timeout: float = 5.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    async def check(self, text: str) -> dict[str, Any]:
        """Check text against Lakera Guard. Returns pass/fail with category."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    LAKERA_API_URL,
                    json={"input": text},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                response.raise_for_status()
                data = response.json()

            # Lakera Guard v2 response structure
            flagged = data.get("flagged", False)
            categories = data.get("categories", {})

            if flagged:
                # Find the category with highest score
                top_category = max(categories, key=lambda k: categories[k]) if categories else "unknown"
                confidence = categories.get(top_category, 0.0)

                return {
                    "passed": False,
                    "category": top_category,
                    "confidence": confidence,
                    "categories": categories,
                }

            return {
                "passed": True,
                "category": None,
                "confidence": None,
            }

        except httpx.TimeoutException:
            logger.error("lakera_guard_timeout", timeout=self._timeout)
            # Fail open on timeout -- log but don't block
            return {"passed": True, "category": None, "error": "timeout"}

        except Exception as e:
            logger.error("lakera_guard_error", error=str(e))
            # Fail open on error -- log but don't block
            return {"passed": True, "category": None, "error": str(e)}
