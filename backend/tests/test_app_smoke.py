from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_app_starts_and_dashboard_readiness_is_clean():
    with TestClient(create_app()) as client:
        health = client.get("/health")
        dashboard = client.get("/api/dashboard")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert dashboard.status_code == 200
    assert dashboard.json()["risk"]["decision"] == "ALLOW"
