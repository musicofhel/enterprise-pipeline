"""Feature flag service — deterministic hash-based variant assignment.

Uses a local YAML config file for variant weights and overrides.
No external dependencies (no LaunchDarkly).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

from src.models.audit import AuditActor, AuditActorType, AuditEvent, AuditEventType

if TYPE_CHECKING:
    from src.config.pipeline_config import FeatureFlagConfig
    from src.observability.audit_log import AuditLogService

logger = structlog.get_logger()


class FeatureFlagService:
    """Deterministic hash-based feature flag assignment.

    Assignment priority:
    1. Tenant overrides (exact match)
    2. User overrides (exact match)
    3. Hash-based bucket assignment using variant weights
    """

    def __init__(
        self,
        config: FeatureFlagConfig,
        audit_log: AuditLogService,
    ) -> None:
        self._config = config
        self._audit_log = audit_log
        self._flag_config = self._load_flag_config(config.config_path)

    @staticmethod
    def _load_flag_config(config_path: str) -> dict[str, Any]:
        """Load variant weights and overrides from YAML."""
        path = Path(config_path)
        if not path.exists():
            logger.warning("feature_flag_config_not_found", path=config_path)
            return {
                "variants": [{"name": "control", "weight": 1.0}],
                "user_overrides": {},
                "tenant_overrides": {},
            }
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return data

    @staticmethod
    def _hash_to_bucket(user_id: str) -> float:
        """Deterministic hash of user_id to [0, 1) bucket."""
        hex_prefix = hashlib.md5(user_id.encode()).hexdigest()[:8]
        return (int(hex_prefix, 16) % 10000) / 10000.0

    def get_variant(self, user_id: str, tenant_id: str | None = None) -> str:
        """Resolve the variant for a user/tenant pair.

        Returns variant name (e.g., "control" or "treatment_a").
        """
        if not self._config.enabled:
            return self._config.default_variant

        tenant_overrides: dict[str, str] = self._flag_config.get("tenant_overrides", {})
        user_overrides: dict[str, str] = self._flag_config.get("user_overrides", {})
        variants: list[dict[str, Any]] = self._flag_config.get("variants", [])

        # 1. Tenant override
        if tenant_id and tenant_id in tenant_overrides:
            variant = tenant_overrides[tenant_id]
            self._log_assignment(user_id, tenant_id, variant, reason="tenant_override")
            return variant

        # 2. User override
        if user_id in user_overrides:
            variant = user_overrides[user_id]
            self._log_assignment(user_id, tenant_id, variant, reason="user_override")
            return variant

        # 3. Hash-based assignment
        bucket = self._hash_to_bucket(user_id)
        cumulative = 0.0
        for v in variants:
            cumulative += v.get("weight", 0)
            if bucket < cumulative:
                variant = str(v["name"])
                self._log_assignment(user_id, tenant_id, variant, reason="hash_assignment")
                return variant

        # Fallback to default
        variant = self._config.default_variant
        self._log_assignment(user_id, tenant_id, variant, reason="fallback")
        return variant

    def _log_assignment(
        self,
        user_id: str,
        tenant_id: str | None,
        variant: str,
        reason: str,
    ) -> None:
        """Log variant assignment to audit trail."""
        event = AuditEvent(
            event_type=AuditEventType.EXPERIMENT_ASSIGNMENT,
            actor=AuditActor(type=AuditActorType.SYSTEM, id="feature_flag_service"),
            details={
                "user_id": user_id,
                "variant": variant,
                "reason": reason,
            },
            tenant_id=tenant_id,
        )
        self._audit_log.log_event(event)
        logger.info(
            "feature_flag_assigned",
            user_id=user_id,
            tenant_id=tenant_id,
            variant=variant,
            reason=reason,
        )
