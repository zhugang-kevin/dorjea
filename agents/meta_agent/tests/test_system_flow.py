from __future__ import annotations

from types import SimpleNamespace

from agents.meta_agent import memory_system
import agents.runtime.agent_runtime as agent_runtime_module
from agents.runtime.agent_runtime import AgentRuntime


def test_memory_helpers_recall_relevant_context(tmp_path, monkeypatch):
    memory_file = tmp_path / "agent_memory.jsonl"
    monkeypatch.setattr(memory_system, "MEMORY_FILE", str(memory_file))

    memory_system.store_task_result_memory(
        "demo_agent",
        "user@example.com",
        "Summarize the workflow state",
        "Workflow state is healthy and fully synchronized.",
        tags=["workflow"],
        context="task_id=t-1",
    )
    memory_system.store_task_result_memory(
        "demo_agent",
        "user@example.com",
        "Draft a landing page",
        "Landing page draft is ready.",
        tags=["marketing"],
        context="task_id=t-2",
    )

    context = memory_system.build_memory_context(
        "demo_agent",
        "user@example.com",
        query="workflow health",
        limit=2,
    )

    assert "Relevant memory:" in context
    assert "Workflow state is healthy" in context
    assert "Landing page draft" not in context


def test_runtime_run_task_returns_route_memory_and_validation(monkeypatch):
    captured_memory_calls: list[dict] = []

    class DummyReliableResult:
        def __init__(self):
            self.response = SimpleNamespace(
                error="",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                text="Workflow summary complete with workflow status and next actions.",
                provider="test-provider",
            )
            self.confidence = 0.88
            self.validation_errors = []

        def model_dump(self):
            return {
                "confidence": self.confidence,
                "validation_errors": self.validation_errors,
                "attempts": 1,
                "used_fallback": False,
            }

    class DummySandbox:
        def get_resource_limits(self):
            return {"max_tokens_per_task": 4000}

        def can_create_agents(self):
            return False

        def can_modify_core(self):
            return False

    monkeypatch.setattr(
        agent_runtime_module,
        "get_agent",
        lambda name: {
            "name": name,
            "status": "active",
            "mission": "Handle operations tasks reliably.",
            "allowed_tools": ["filesystem_server"],
            "default_model": "claude-sonnet-4-6",
            "fallback_model": "gpt-4o",
            "token_budget": 4000,
            "department": "operations",
        },
    )
    monkeypatch.setattr(agent_runtime_module, "is_safe", lambda task, agent_id=None: (True, ""))
    monkeypatch.setattr(agent_runtime_module, "create_sandbox", lambda agent_name: DummySandbox())
    monkeypatch.setattr(agent_runtime_module, "is_within_budget", lambda used, budget=None: True)
    monkeypatch.setattr(agent_runtime_module, "track_tokens", lambda **kwargs: None)
    monkeypatch.setattr(agent_runtime_module, "record_task_result", lambda **kwargs: None)
    monkeypatch.setattr(agent_runtime_module, "write_audit_entry", lambda entry: None)
    monkeypatch.setattr(agent_runtime_module, "call_with_reliability", lambda **kwargs: DummyReliableResult())
    monkeypatch.setattr(
        agent_runtime_module,
        "build_memory_context",
        lambda agent_id, user_email, query="", limit=3: "Relevant memory:\n1. Prior workflow state is cached.",
    )
    monkeypatch.setattr(
        agent_runtime_module,
        "store_task_result_memory",
        lambda agent_id, user_email, task_instruction, output, **kwargs: captured_memory_calls.append(
            {
                "agent_id": agent_id,
                "user_email": user_email,
                "task_instruction": task_instruction,
                "output": output,
                "extra": kwargs,
            }
        ),
    )

    runtime = AgentRuntime()
    result = runtime.run_task(
        "demo_agent",
        "Summarize the workflow status and next actions",
        task_id="task-123",
        user_email="user@example.com",
        validation_rules=[{"type": "contains", "value": "workflow"}],
    )

    assert result["status"] == "SUCCESS"
    assert result["route"]["selected_model"] == "claude-sonnet-4-6"
    assert result["memory_context_used"] is True
    assert result["validation"]["passed"] is True
    assert captured_memory_calls
    assert captured_memory_calls[0]["user_email"] == "user@example.com"
