from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents.meta_agent import api as api_module


def test_run_agent_task_uses_gateway_task_id(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")
    monkeypatch.setattr(api_module, "enforce_daily_tokens_allowance", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_module, "is_safe", lambda task, agent_id=None: (True, ""))
    monkeypatch.setattr(api_module, "rate_limiter", SimpleNamespace(is_allowed=lambda actor: True))
    monkeypatch.setattr(
        api_module.gateway,
        "validate_and_admit",
        lambda request, source="founder", parent_task_id=None, task_owner=None, route_metadata=None: (
            {
                "task_id": "gateway-task-1",
                "source": source,
                "parent_task_id": parent_task_id,
                "task_owner": task_owner,
                "route_metadata": route_metadata,
            },
            [],
        ),
    )

    def fake_run_task(agent_name, task_instruction, task_id=None, user_email=None, validation_rules=None):
        captured["agent_name"] = agent_name
        captured["task_instruction"] = task_instruction
        captured["task_id"] = task_id
        captured["user_email"] = user_email
        return {"status": "SUCCESS", "task_id": task_id, "agent_name": agent_name, "output": "ok"}

    monkeypatch.setattr(api_module.runtime, "run_task", fake_run_task)

    result = api_module.run_agent_task(
        "demo_agent",
        api_module.RunTaskRequest(task="Run a safe task"),
        authorization="Bearer token",
    )

    assert result["status"] == "SUCCESS"
    assert captured["task_id"] == "gateway-task-1"
    assert captured["agent_name"] == "demo_agent"
    assert captured["user_email"] == "user@example.com"


def test_run_agent_task_async_queues_gateway_task_id(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")
    monkeypatch.setattr(api_module, "enforce_daily_tokens_allowance", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_module, "is_safe", lambda task, agent_id=None: (True, ""))
    monkeypatch.setattr(api_module, "rate_limiter", SimpleNamespace(is_allowed=lambda actor: True))
    monkeypatch.setattr(
        api_module.gateway,
        "validate_and_admit",
        lambda request, source="founder", parent_task_id=None, task_owner=None, route_metadata=None: (
            {
                "task_id": "gateway-task-2",
                "source": source,
                "parent_task_id": parent_task_id,
                "task_owner": task_owner,
                "route_metadata": route_metadata,
            },
            [],
        ),
    )
    monkeypatch.setattr(
        api_module.task_queue,
        "enqueue_agent_task",
        lambda **kwargs: {
            "task_id": kwargs["task_id"],
            "status": "pending",
            "agent_name": kwargs["agent_name"],
        },
    )
    monkeypatch.setattr(api_module.task_queue, "get_queue_stats", lambda: {"backend": "filesystem"})

    result = api_module.run_agent_task_async(
        "demo_agent",
        api_module.RunTaskRequest(task="Queue a safe task"),
        authorization="Bearer token",
    )

    assert result.task_id == "gateway-task-2"
    assert result.status == "pending"
    assert result.agent_name == "demo_agent"


def test_run_agent_task_rejects_missing_bearer_email(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "")

    with pytest.raises(HTTPException) as exc:
        api_module.run_agent_task(
            "demo_agent",
            api_module.RunTaskRequest(task="Run a safe task"),
            authorization="Bearer token",
        )

    assert exc.value.status_code == 401
    assert "需要先登录" in str(exc.value.detail)


def test_run_agent_task_rejects_short_task_before_runtime(monkeypatch):
    called = {"runtime": False}

    def fake_run_task(*args, **kwargs):
        called["runtime"] = True
        return {"status": "SUCCESS"}

    monkeypatch.setattr(api_module.runtime, "run_task", fake_run_task)

    with pytest.raises(HTTPException) as exc:
        api_module.run_agent_task(
            "demo_agent",
            api_module.RunTaskRequest(task="bad"),
            authorization="Bearer token",
        )

    assert exc.value.status_code == 400
    assert "至少 5 个字符" in str(exc.value.detail)
    assert called["runtime"] is False


def test_run_agent_task_rejects_gateway_admission_errors(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "user@example.com")
    monkeypatch.setattr(api_module, "enforce_daily_tokens_allowance", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_module, "is_safe", lambda task, agent_id=None: (True, ""))
    monkeypatch.setattr(api_module, "rate_limiter", SimpleNamespace(is_allowed=lambda actor: True))
    monkeypatch.setattr(
        api_module.gateway,
        "validate_and_admit",
        lambda request, source="founder", parent_task_id=None, task_owner=None, route_metadata=None: (
            {"task_id": "gateway-task-3"},
            ["policy denied"],
        ),
    )

    with pytest.raises(HTTPException) as exc:
        api_module.run_agent_task(
            "demo_agent",
            api_module.RunTaskRequest(task="Run a safe task"),
            authorization="Bearer token",
        )

    assert exc.value.status_code == 400
    assert "policy denied" in str(exc.value.detail)


def test_run_agent_task_async_rejects_missing_bearer_email(monkeypatch):
    monkeypatch.setattr(api_module, "parse_bearer_email", lambda authorization: "")

    with pytest.raises(HTTPException) as exc:
        api_module.run_agent_task_async(
            "demo_agent",
            api_module.RunTaskRequest(task="Queue a safe task"),
            authorization="Bearer token",
        )

    assert exc.value.status_code == 401
    assert "需要先登录" in str(exc.value.detail)
