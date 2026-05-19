from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from agents.meta_agent import api as api_module
from agents.meta_agent import plan_enforcement as pe_module


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


def test_system_build_order_complete_requires_login():
    client = TestClient(api_module.app)

    response = client.post("/system/build-order/complete", json={"phase": "backend"})

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "需要登录" in detail


def test_system_build_order_complete_requires_admin(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")
    monkeypatch.setattr(api_module, "pe_load_user", lambda email: {"email": email, "is_admin": False, "is_owner": False})
    client = TestClient(api_module.app)

    response = client.post(
        "/system/build-order/complete",
        json={"phase": "backend"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    detail = response.json().get("detail", "")
    assert "仅管理员可推进构建阶段" in detail


def test_system_build_order_reset_requires_admin(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")
    monkeypatch.setattr(api_module, "pe_load_user", lambda email: {"email": email, "is_admin": False, "is_owner": False})
    client = TestClient(api_module.app)

    response = client.post("/system/build-order/reset", headers={"Authorization": "Bearer token"})

    assert response.status_code == 403
    detail = response.json().get("detail", "")
    assert "仅管理员可重置构建阶段" in detail


def test_system_budget_requires_login():
    client = TestClient(api_module.app)

    response = client.post("/system/budget", json={"daily_budget": 1000})

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "需要登录" in detail


def test_system_budget_rejects_non_admin(monkeypatch):
    monkeypatch.setattr(pe_module, "parse_bearer_email", lambda authorization: "user@example.com")
    monkeypatch.setattr(pe_module, "load_user", lambda email: {"email": email, "is_admin": False, "is_owner": False})
    client = TestClient(api_module.app)

    response = client.post(
        "/system/budget",
        json={"daily_budget": 1000},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    detail = response.json().get("detail", "")
    assert "仅管理员可修改预算" in detail


def test_system_budget_rejects_invalid_range_for_admin(monkeypatch):
    monkeypatch.setattr(pe_module, "parse_bearer_email", lambda authorization: "owner@example.com")
    monkeypatch.setattr(pe_module, "load_user", lambda email: {"email": email, "is_admin": True, "is_owner": True})
    client = TestClient(api_module.app)

    response = client.post(
        "/system/budget",
        json={"daily_budget": -1},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "预算值超出合法范围" in detail


def test_system_budget_accepts_valid_admin_update(monkeypatch):
    monkeypatch.setattr(pe_module, "parse_bearer_email", lambda authorization: "owner@example.com")
    monkeypatch.setattr(pe_module, "load_user", lambda email: {"email": email, "is_admin": True, "is_owner": True})

    with tempfile.TemporaryDirectory() as tmp:
        current = Path.cwd()
        tmp_path = Path(tmp)
        (tmp_path / ".env").write_text("DAILY_TOKEN_BUDGET=50000\n", encoding="utf-8")
        try:
            # The route writes to ".env" in current working directory.
            import os

            os.chdir(tmp_path)
            client = TestClient(api_module.app)
            response = client.post(
                "/system/budget",
                json={"daily_budget": 12345},
                headers={"Authorization": "Bearer token"},
            )
        finally:
            os.chdir(current)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["daily_budget"] == 12345


def test_affiliate_link_requires_login():
    client = TestClient(api_module.app)

    response = client.get("/affiliate/link")

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "缺少令牌" in detail


def test_affiliate_link_enforces_referral_feature(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")

    def deny_feature(email, feature):
        raise api_module.HTTPException(status_code=403, detail="当前套餐不支持该功能。")

    monkeypatch.setattr(api_module, "enforce_plan_feature", deny_feature)
    client = TestClient(api_module.app)

    response = client.get("/affiliate/link", headers={"Authorization": "Bearer token"})

    assert response.status_code == 403
    detail = response.json().get("detail", "")
    assert "不支持" in detail


def test_affiliate_stats_requires_login():
    client = TestClient(api_module.app)

    response = client.get("/affiliate/stats")

    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "缺少令牌" in detail
