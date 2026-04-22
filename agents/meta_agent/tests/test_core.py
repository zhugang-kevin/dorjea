import pytest
import uuid
from agents.meta_agent.models import (
    TaskSpec, AgentSpec, VerificationResult,
    TestResult, AuditEntry, FounderReport, MetaAgentState
)
from agents.meta_agent.state import MetaAgentState as StateDict
from agents.meta_agent.registry import agent_exists, register_agent, get_agent, update_agent_status
from agents.meta_agent.audit_logger import write_audit_entry, read_last_entry
from agents.meta_agent.graph import meta_agent_graph


# ── MODEL TESTS ───────────────────────────────────────────────────────────────

def test_task_spec_valid():
    spec = TaskSpec(
        agent_name="test_agent",
        agent_role="Test Role",
        agent_mission="This is a test mission for the agent.",
        allowed_tools=["filesystem_server"],
        founder_request="Create a test agent for testing purposes.",
    )
    assert spec.agent_name == "test_agent"
    assert spec.token_budget == 10000


def test_task_spec_name_normalised():
    spec = TaskSpec(
        agent_name="Test-Agent",
        agent_role="Test Role",
        agent_mission="This is a test mission for the agent.",
        allowed_tools=["filesystem_server"],
        founder_request="Create a test agent for testing purposes.",
    )
    assert spec.agent_name == "test_agent"


def test_task_spec_token_budget_limit():
    with pytest.raises(Exception):
        TaskSpec(
            agent_name="test_agent",
            agent_role="Test Role",
            agent_mission="This is a test mission for the agent.",
            allowed_tools=["filesystem_server"],
            founder_request="Create a test agent.",
            token_budget=99999,
        )


def test_agent_spec_valid():
    spec = AgentSpec(
        agent_name="content_writer_agent",
        mission="Write high quality content for the company blog.",
        responsibilities=["Write blog posts", "Proofread content"],
        non_responsibilities=["Publish directly", "Manage CMS"],
        allowed_tools=["filesystem_server"],
    )
    assert spec.agent_name == "content_writer_agent"
    assert spec.version == "1.0"


def test_verification_result_pass():
    result = VerificationResult(status="PASS")
    assert result.status == "PASS"


def test_verification_result_fail():
    result = VerificationResult(status="FAIL", issues=["Missing mission"])
    assert result.status == "FAIL"
    assert len(result.issues) == 1


def test_verification_result_invalid_status():
    with pytest.raises(Exception):
        VerificationResult(status="UNKNOWN")


def test_founder_report_valid():
    report = FounderReport(
        task_id=str(uuid.uuid4()),
        agent_name="test_agent",
        status="SUCCESS",
        summary="Agent created successfully.",
        rollback_command="git revert HEAD",
    )
    assert report.status == "SUCCESS"
    assert report.completed_at != ""


def test_audit_entry_auto_timestamp():
    entry = AuditEntry(
        agent_id="test-id",
        task_id="task-id",
        action="test_action",
    )
    assert entry.logged_at != ""


# ── REGISTRY TESTS ────────────────────────────────────────────────────────────

def test_register_and_get_agent():
    unique_name = f"test_agent_{uuid.uuid4().hex[:8]}"
    result = register_agent(
        name=unique_name,
        mission="Test mission for automated testing.",
        allowed_tools=["filesystem_server"],
        default_model="claude-sonnet-4-6",
        fallback_model="gpt-4o",
        token_budget=5000,
        spec_yaml="agent_name: test",
        department="engineering",
    )
    assert result["success"] is True
    assert result["agent_id"] is not None

    agent = get_agent(unique_name)
    assert agent is not None
    assert agent["name"] == unique_name


def test_agent_exists_true():
    unique_name = f"exists_agent_{uuid.uuid4().hex[:8]}"
    register_agent(
        name=unique_name,
        mission="Test mission.",
        allowed_tools=["filesystem_server"],
        default_model="claude-sonnet-4-6",
        fallback_model="gpt-4o",
        token_budget=5000,
        spec_yaml="",
        department="general",
    )
    assert agent_exists(unique_name) is True


def test_agent_exists_false():
    assert agent_exists("nonexistent_agent_xyz_123") is False


def test_update_agent_status():
    unique_name = f"status_agent_{uuid.uuid4().hex[:8]}"
    register_agent(
        name=unique_name,
        mission="Test mission.",
        allowed_tools=["filesystem_server"],
        default_model="claude-sonnet-4-6",
        fallback_model="gpt-4o",
        token_budget=5000,
        spec_yaml="",
        department="general",
    )
    success = update_agent_status(unique_name, "frozen")
    assert success is True


# ── AUDIT LOGGER TESTS ────────────────────────────────────────────────────────

def test_write_and_read_audit_entry():
    entry = AuditEntry(
        agent_id="test-agent-id",
        task_id=str(uuid.uuid4()),
        action="test_write_audit",
        details={"test": True},
        tokens_used=100,
        success=True,
    )
    write_audit_entry(entry)
    last = read_last_entry()
    assert last is not None
    assert last.action == "test_write_audit"


# ── GRAPH TESTS ───────────────────────────────────────────────────────────────

def test_graph_compiled():
    assert meta_agent_graph is not None


def test_graph_has_nodes():
    graph_dict = meta_agent_graph.get_graph().to_json()
    assert "nodes" in graph_dict