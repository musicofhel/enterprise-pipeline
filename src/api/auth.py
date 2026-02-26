"""Minimal API-key → role authentication for compliance-gated endpoints.

Callers pass ``Authorization: Bearer <api-key>`` or ``X-API-Key: <key>``.
The key is looked up in a static registry (env-configurable) that maps
each key to an RBAC Role.  No external identity provider yet — this is
the simplest enforcement that actually blocks unauthorized callers.
"""
from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request

from src.models.rbac import Permission, PermissionChecker, Role

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

# API_KEY_ROLES is a semicolon-separated list of key=role pairs.
# Example env value: "sk-admin-1=security_admin;sk-worker-1=pipeline_worker"
# Parsed once at import time.
_RAW = os.environ.get("API_KEY_ROLES", "")
API_KEY_ROLES: dict[str, Role] = {}
for _pair in _RAW.split(";"):
    _pair = _pair.strip()
    if "=" in _pair:
        _k, _v = _pair.split("=", 1)
        with contextlib.suppress(ValueError):
            API_KEY_ROLES[_k.strip()] = Role(_v.strip())


def _extract_api_key(request: Request) -> str | None:
    """Extract API key from Authorization header or X-API-Key."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.headers.get("x-api-key")


def _resolve_role(api_key: str | None) -> Role:
    """Resolve an API key to a Role.  Raises 401 if key is missing/unknown."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    role = API_KEY_ROLES.get(api_key)
    if role is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return role


def require_permission(
    permission: Permission,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """FastAPI dependency factory — returns a callable that enforces *permission*.

    Usage::

        @router.delete(
            "/users/{user_id}/data",
            dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))],
        )
        async def delete_user_data(...): ...
    """

    async def _checker(request: Request) -> None:
        api_key = _extract_api_key(request)
        role = _resolve_role(api_key)
        checker = PermissionChecker(role)
        if not checker.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Role {role.value} does not have {permission.value} permission",
            )

    return _checker
