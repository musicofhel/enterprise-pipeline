from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING, Any

import structlog

from src.pipeline.safety.injection_detector import InjectionDetector
from src.pipeline.safety.pii_detector import PIIDetector

if TYPE_CHECKING:
    from src.pipeline.safety.lakera_guard import LakeraGuardClient

logger = structlog.get_logger()


class SafetyChecker:
    """Layered input safety: regex patterns -> Lakera Guard API -> PII detection."""

    def __init__(
        self,
        injection_detector: InjectionDetector | None = None,
        lakera_client: LakeraGuardClient | None = None,
        pii_detector: PIIDetector | None = None,
    ) -> None:
        self._injection = injection_detector or InjectionDetector()
        self._lakera = lakera_client
        self._pii = pii_detector or PIIDetector()

    async def check_input(self, text: str, user_id: str) -> dict[str, Any]:
        """Run all safety layers. Returns on first block."""
        start = time.monotonic()
        input_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Layer 1: Regex/heuristic injection detection (<10ms target)
        layer1_result = self._injection.check(text)
        if not layer1_result["passed"]:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                "input_blocked",
                layer="injection_detector",
                detection=layer1_result["detection"],
                input_hash=input_hash,
                user_id=user_id,
                latency_ms=elapsed_ms,
            )
            return {
                "passed": False,
                "reason": f"prompt_injection_detected: {layer1_result['detection']}",
                "layer": "layer_1_regex",
                "skipped": False,
            }

        # Layer 2: Lakera Guard ML-based detection (<50ms target)
        if self._lakera:
            layer2_result = await self._lakera.check(text)
            if not layer2_result["passed"]:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.warning(
                    "input_blocked",
                    layer="lakera_guard",
                    category=layer2_result.get("category"),
                    confidence=layer2_result.get("confidence"),
                    input_hash=input_hash,
                    user_id=user_id,
                    latency_ms=elapsed_ms,
                )
                return {
                    "passed": False,
                    "reason": f"lakera_guard_blocked: {layer2_result.get('category', 'unknown')}",
                    "layer": "layer_2_lakera",
                    "confidence": layer2_result.get("confidence"),
                    "skipped": False,
                }

        # PII detection (runs on all inputs, redacts if configured)
        pii_result = self._pii.detect(text)
        if pii_result["has_pii"]:
            logger.info(
                "pii_detected",
                types=pii_result["types"],
                input_hash=input_hash,
                user_id=user_id,
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "passed": True,
            "reason": None,
            "skipped": False,
            "pii_detected": pii_result["has_pii"],
            "pii_types": pii_result.get("types", []),
            "latency_ms": elapsed_ms,
        }
