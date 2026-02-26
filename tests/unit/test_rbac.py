"""Tests for RBAC roles and permissions."""
from __future__ import annotations

import pytest

from src.models.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    PermissionChecker,
    Role,
)


class TestRoles:
    def test_five_roles_defined(self) -> None:
        assert len(Role) == 5

    def test_all_roles_have_permissions(self) -> None:
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"Missing permissions for {role}"
            assert len(ROLE_PERMISSIONS[role]) > 0


class TestPermissionChecker:
    def test_pipeline_worker_can_run_pipeline(self) -> None:
        checker = PermissionChecker(Role.PIPELINE_WORKER)
        assert checker.has_permission(Permission.RUN_PIPELINE)

    def test_pipeline_worker_cannot_delete(self) -> None:
        checker = PermissionChecker(Role.PIPELINE_WORKER)
        assert not checker.can_delete()

    def test_security_admin_can_delete(self) -> None:
        checker = PermissionChecker(Role.SECURITY_ADMIN)
        assert checker.can_delete()

    def test_compliance_officer_can_read_audit(self) -> None:
        checker = PermissionChecker(Role.COMPLIANCE_OFFICER)
        assert checker.can_read_audit()

    @pytest.mark.parametrize(
        "role,expected",
        [
            (Role.PLATFORM_ENGINEER, True),
            (Role.SECURITY_ADMIN, True),
            (Role.ML_ENGINEER, False),
            (Role.PIPELINE_WORKER, False),
            (Role.COMPLIANCE_OFFICER, False),
        ],
    )
    def test_can_change_config(self, role: Role, expected: bool) -> None:
        checker = PermissionChecker(role)
        assert checker.can_change_config() == expected
