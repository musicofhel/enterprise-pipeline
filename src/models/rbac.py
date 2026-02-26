"""RBAC role and permission model.

Matches tech spec Section 6.2 — five roles with explicit permission mappings.
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    PIPELINE_WORKER = "pipeline_worker"
    ML_ENGINEER = "ml_engineer"
    PLATFORM_ENGINEER = "platform_engineer"
    SECURITY_ADMIN = "security_admin"
    COMPLIANCE_OFFICER = "compliance_officer"


class Permission(StrEnum):
    READ_TRACES = "read_traces"
    WRITE_TRACES = "write_traces"
    READ_AUDIT = "read_audit"
    DELETE_USER_DATA = "delete_user_data"
    CHANGE_CONFIG = "change_config"
    MANAGE_MODELS = "manage_models"
    READ_VECTORS = "read_vectors"
    WRITE_VECTORS = "write_vectors"
    READ_FEEDBACK = "read_feedback"
    WRITE_FEEDBACK = "write_feedback"
    RUN_PIPELINE = "run_pipeline"
    VIEW_EXPERIMENTS = "view_experiments"
    MANAGE_EXPERIMENTS = "manage_experiments"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.PIPELINE_WORKER: frozenset({
        Permission.RUN_PIPELINE,
        Permission.READ_VECTORS,
        Permission.WRITE_VECTORS,
        Permission.WRITE_TRACES,
        Permission.READ_TRACES,
        Permission.WRITE_FEEDBACK,
    }),
    Role.ML_ENGINEER: frozenset({
        Permission.RUN_PIPELINE,
        Permission.READ_VECTORS,
        Permission.WRITE_VECTORS,
        Permission.READ_TRACES,
        Permission.WRITE_TRACES,
        Permission.MANAGE_MODELS,
        Permission.READ_FEEDBACK,
        Permission.WRITE_FEEDBACK,
        Permission.VIEW_EXPERIMENTS,
        Permission.MANAGE_EXPERIMENTS,
    }),
    Role.PLATFORM_ENGINEER: frozenset({
        Permission.RUN_PIPELINE,
        Permission.READ_VECTORS,
        Permission.WRITE_VECTORS,
        Permission.READ_TRACES,
        Permission.WRITE_TRACES,
        Permission.CHANGE_CONFIG,
        Permission.MANAGE_MODELS,
        Permission.READ_FEEDBACK,
        Permission.VIEW_EXPERIMENTS,
        Permission.MANAGE_EXPERIMENTS,
    }),
    Role.SECURITY_ADMIN: frozenset({
        Permission.READ_TRACES,
        Permission.READ_AUDIT,
        Permission.READ_VECTORS,
        Permission.DELETE_USER_DATA,
        Permission.CHANGE_CONFIG,
        Permission.READ_FEEDBACK,
        Permission.VIEW_EXPERIMENTS,
    }),
    Role.COMPLIANCE_OFFICER: frozenset({
        Permission.READ_TRACES,
        Permission.READ_AUDIT,
        Permission.DELETE_USER_DATA,
        Permission.READ_VECTORS,
        Permission.READ_FEEDBACK,
        Permission.VIEW_EXPERIMENTS,
    }),
}


class PermissionChecker:
    """Check whether a role has a given permission."""

    def __init__(self, role: Role) -> None:
        self._role = role
        self._permissions = ROLE_PERMISSIONS.get(role, frozenset())

    @property
    def role(self) -> Role:
        return self._role

    def has_permission(self, permission: Permission) -> bool:
        return permission in self._permissions

    def can_delete(self) -> bool:
        return self.has_permission(Permission.DELETE_USER_DATA)

    def can_read_audit(self) -> bool:
        return self.has_permission(Permission.READ_AUDIT)

    def can_change_config(self) -> bool:
        return self.has_permission(Permission.CHANGE_CONFIG)
