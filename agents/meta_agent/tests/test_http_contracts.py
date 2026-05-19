from __future__ import annotations

from fastapi.testclient import TestClient

from agents.meta_agent import api as api_module


def test_run_endpoint_returns_401_without_login(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "")
    client = TestClient(api_module.app)

    response = client.post("/agents/demo_agent/run", json={"task": "Run a safe task"})

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "登录" in detail


def test_run_endpoint_returns_400_for_short_task(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")
    client = TestClient(api_module.app)

    response = client.post(
        "/agents/demo_agent/run",
        json={"task": "bad"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "至少 5 个字符" in detail


def test_run_async_endpoint_returns_401_without_login(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "")
    client = TestClient(api_module.app)

    response = client.post("/agents/demo_agent/run/async", json={"task": "Queue safe task"})

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "登录" in detail


def test_auth_me_rejects_missing_authorization_header():
    client = TestClient(api_module.app)

    response = client.get("/auth/me")

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "缺少令牌" in detail

