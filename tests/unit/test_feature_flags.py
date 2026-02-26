"""Tests for feature flag service — 10 tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from src.config.pipeline_config import FeatureFlagConfig
from src.experimentation.feature_flags import FeatureFlagService
from src.models.audit import AuditEventType
from src.observability.audit_log import AuditLogService

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def audit_log(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


@pytest.fixture
def flags_yaml(tmp_path: Path) -> Path:
    config = {
        "variants": [
            {"name": "control", "weight": 0.9},
            {"name": "treatment_a", "weight": 0.1},
        ],
        "user_overrides": {"override-user": "treatment_a"},
        "tenant_overrides": {"tenant-beta": "treatment_a"},
    }
    path = tmp_path / "flags.yaml"
    path.write_text(yaml.dump(config))
    return path


@pytest.fixture
def ff_config(flags_yaml: Path) -> FeatureFlagConfig:
    return FeatureFlagConfig(enabled=True, config_path=str(flags_yaml))


@pytest.fixture
def service(ff_config: FeatureFlagConfig, audit_log: AuditLogService) -> FeatureFlagService:
    return FeatureFlagService(config=ff_config, audit_log=audit_log)


class TestFeatureFlagService:
    def test_disabled_returns_default(self, audit_log: AuditLogService, flags_yaml: Path) -> None:
        config = FeatureFlagConfig(enabled=False, config_path=str(flags_yaml))
        svc = FeatureFlagService(config=config, audit_log=audit_log)
        assert svc.get_variant("any-user") == "control"

    def test_tenant_override_takes_precedence(self, service: FeatureFlagService) -> None:
        variant = service.get_variant("random-user", tenant_id="tenant-beta")
        assert variant == "treatment_a"

    def test_user_override_takes_precedence_over_hash(
        self, service: FeatureFlagService
    ) -> None:
        variant = service.get_variant("override-user")
        assert variant == "treatment_a"

    def test_hash_is_deterministic(self, service: FeatureFlagService) -> None:
        v1 = service.get_variant("deterministic-user-42")
        v2 = service.get_variant("deterministic-user-42")
        assert v1 == v2

    def test_hash_returns_valid_variant(self, service: FeatureFlagService) -> None:
        variant = service.get_variant("some-user")
        assert variant in ("control", "treatment_a")

    def test_90_10_split_approximate(self, service: FeatureFlagService) -> None:
        """With 1000 users, ~90% should be control, ~10% treatment_a."""
        counts: dict[str, int] = {"control": 0, "treatment_a": 0}
        for i in range(1000):
            v = service.get_variant(f"user-{i}")
            counts[v] = counts.get(v, 0) + 1
        # Allow 5% tolerance
        assert counts["control"] > 800, f"control={counts['control']}"
        assert counts["treatment_a"] > 50, f"treatment_a={counts['treatment_a']}"

    def test_audit_log_created_on_assignment(
        self, service: FeatureFlagService, audit_log: AuditLogService
    ) -> None:
        service.get_variant("audit-user")
        events = audit_log.list_events(event_type=AuditEventType.EXPERIMENT_ASSIGNMENT)
        assert len(events) >= 1
        assert events[0].details["user_id"] == "audit-user"

    def test_missing_config_file_uses_defaults(
        self, audit_log: AuditLogService
    ) -> None:
        config = FeatureFlagConfig(enabled=True, config_path="/nonexistent/flags.yaml")
        svc = FeatureFlagService(config=config, audit_log=audit_log)
        variant = svc.get_variant("any-user")
        assert variant == "control"

    def test_hash_bucket_range(self) -> None:
        """Hash bucket should be in [0, 1)."""
        for i in range(100):
            bucket = FeatureFlagService._hash_to_bucket(f"user-{i}")
            assert 0.0 <= bucket < 1.0

    def test_tenant_override_logged_with_tenant_id(
        self, service: FeatureFlagService, audit_log: AuditLogService
    ) -> None:
        service.get_variant("any-user", tenant_id="tenant-beta")
        events = audit_log.list_events(event_type=AuditEventType.EXPERIMENT_ASSIGNMENT)
        assert any(e.tenant_id == "tenant-beta" for e in events)
