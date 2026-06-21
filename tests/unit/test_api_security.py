"""Security checks for admin and destructive API operations."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from codegraph.agent.tools.stats import tool_stats_collector
from codegraph.api.router import api_router
from codegraph.config import settings


def _client(monkeypatch, admin_key: str = "test-admin-key") -> TestClient:
    monkeypatch.setattr(settings, "admin_api_key", admin_key)
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    return TestClient(app)


def test_admin_health_requires_api_key_when_configured(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/v1/admin/health")

    assert response.status_code == 401


def test_admin_health_accepts_valid_api_key(monkeypatch):
    client = _client(monkeypatch)

    response = client.get(
        "/api/v1/admin/health",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    assert response.status_code in {200, 500}
    assert response.status_code != 401


def test_reset_tool_stats_requires_typed_confirmation(monkeypatch):
    client = _client(monkeypatch)
    tool_stats_collector.record_call("demo_tool", duration_ms=12, success=True)

    response = client.post(
        "/api/v1/agent/tools/stats/reset",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    assert response.status_code == 400
    assert tool_stats_collector.get_tool_stats("demo_tool") is not None


def test_reset_tool_stats_with_admin_key_and_confirmation(monkeypatch):
    client = _client(monkeypatch)
    tool_stats_collector.record_call("demo_tool", duration_ms=12, success=True)

    response = client.post(
        "/api/v1/agent/tools/stats/reset?confirmation=RESET_TOOL_STATS",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    assert response.status_code == 200
    assert tool_stats_collector.get_tool_stats("demo_tool") is None


