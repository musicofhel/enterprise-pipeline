"""Tests for API key → role auth enforcement."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.auth import require_permission
from src.models.rbac import Permission, Role


@pytest.fixture
def app_with_protected_route() -> FastAPI:
    """FastAPI app with a single DELETE_USER_DATA-protected route."""
    app = FastAPI()

    @app.delete(
        "/test-delete",
        dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))],
    )
    async def protected_delete() -> dict[str, str]:
        return {"ok": "deleted"}

    @app.post(
        "/test-feedback",
        dependencies=[Depends(require_permission(Permission.WRITE_FEEDBACK))],
    )
    async def protected_feedback() -> dict[str, str]:
        return {"ok": "recorded"}

    return app


@pytest.fixture
def client(app_with_protected_route: FastAPI) -> TestClient:
    return TestClient(app_with_protected_route)


class TestAuthNoKey:
    def test_missing_key_returns_401(self, client: TestClient) -> None:
        resp = client.delete("/test-delete")
        assert resp.status_code == 401
        assert "Missing API key" in resp.json()["detail"]

    def test_invalid_key_returns_401(self, client: TestClient) -> None:
        resp = client.delete(
            "/test-delete", headers={"Authorization": "Bearer sk-bogus"}
        )
        assert resp.status_code == 401
        assert "Invalid API key" in resp.json()["detail"]


class TestAuthRBAC:
    @patch(
        "src.api.auth.API_KEY_ROLES",
        {"sk-admin": Role.SECURITY_ADMIN, "sk-worker": Role.PIPELINE_WORKER},
    )
    def test_security_admin_can_delete(self, client: TestClient) -> None:
        resp = client.delete(
            "/test-delete", headers={"Authorization": "Bearer sk-admin"}
        )
        assert resp.status_code == 200

    @patch(
        "src.api.auth.API_KEY_ROLES",
        {"sk-admin": Role.SECURITY_ADMIN, "sk-worker": Role.PIPELINE_WORKER},
    )
    def test_pipeline_worker_cannot_delete(self, client: TestClient) -> None:
        resp = client.delete(
            "/test-delete", headers={"Authorization": "Bearer sk-worker"}
        )
        assert resp.status_code == 403

    @patch(
        "src.api.auth.API_KEY_ROLES",
        {"sk-compliance": Role.COMPLIANCE_OFFICER},
    )
    def test_compliance_officer_can_delete(self, client: TestClient) -> None:
        resp = client.delete(
            "/test-delete", headers={"Authorization": "Bearer sk-compliance"}
        )
        assert resp.status_code == 200

    @patch(
        "src.api.auth.API_KEY_ROLES",
        {"sk-worker": Role.PIPELINE_WORKER},
    )
    def test_pipeline_worker_can_write_feedback(self, client: TestClient) -> None:
        resp = client.post(
            "/test-feedback", headers={"Authorization": "Bearer sk-worker"}
        )
        assert resp.status_code == 200

    @patch(
        "src.api.auth.API_KEY_ROLES",
        {"sk-admin": Role.SECURITY_ADMIN},
    )
    def test_x_api_key_header_works(self, client: TestClient) -> None:
        resp = client.delete(
            "/test-delete", headers={"X-API-Key": "sk-admin"}
        )
        assert resp.status_code == 200

    @patch(
        "src.api.auth.API_KEY_ROLES",
        {"sk-ml": Role.ML_ENGINEER},
    )
    def test_ml_engineer_cannot_delete(self, client: TestClient) -> None:
        resp = client.delete(
            "/test-delete", headers={"Authorization": "Bearer sk-ml"}
        )
        assert resp.status_code == 403
        assert "does not have" in resp.json()["detail"]
