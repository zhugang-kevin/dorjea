from __future__ import annotations

import pytest

from agents.meta_agent import build_contract
from agents.meta_agent.model_handoff import get_model_guidance
from agents.runtime.ai_clients import MiniMaxDomesticClient, _make_named_client


def test_frontend_blocked_until_backend_and_api_contract(tmp_path, monkeypatch):
    state_file = tmp_path / "project_state.json"
    monkeypatch.setattr(build_contract, "STATE_FILE", state_file)
    build_contract.save_build_state(
        {
            "phases": build_contract.PHASES,
            "completed": ["architecture"],
            "current_phase": "backend",
            "notes": "test",
        }
    )

    error = build_contract.enforce_request_build_order("Build the frontend dashboard UI now")

    assert error is not None
    assert "backend" in error
    assert "api_contract" in error


def test_mark_phase_complete_advances_current_phase(tmp_path, monkeypatch):
    state_file = tmp_path / "project_state.json"
    monkeypatch.setattr(build_contract, "STATE_FILE", state_file)
    build_contract.reset_build_state()

    state = build_contract.mark_phase_complete("backend")

    assert "architecture" in state["completed"]
    assert "backend" in state["completed"]
    assert state["current_phase"] == "api_contract"


def test_model_guidance_returns_recommended_model(tmp_path, monkeypatch):
    state_file = tmp_path / "project_state.json"
    monkeypatch.setattr(build_contract, "STATE_FILE", state_file)
    build_contract.save_build_state(
        {
            "phases": build_contract.PHASES,
            "completed": ["architecture", "backend"],
            "current_phase": "api_contract",
            "notes": "test",
        }
    )

    guidance = get_model_guidance()

    assert guidance["next_required_phase"] == "api_contract"
    assert guidance["recommended_model"] == "claude"


def test_named_client_supports_minimax():
    client = _make_named_client("minimax")
    assert isinstance(client, MiniMaxDomesticClient)


def test_mark_phase_complete_rejects_unknown_phase(tmp_path, monkeypatch):
    state_file = tmp_path / "project_state.json"
    monkeypatch.setattr(build_contract, "STATE_FILE", state_file)
    build_contract.reset_build_state()

    with pytest.raises(ValueError):
        build_contract.mark_phase_complete("not_a_real_phase")
