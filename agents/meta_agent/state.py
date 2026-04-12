"""
state.py — LangGraph TypedDict state for the Meta-Agent workflow.
Uses LangGraph 1.1.x TypedDict-based state.
This is the single object passed between all 9 nodes.
"""
from __future__ import annotations
from typing import Optional, List, Any
from typing_extensions import TypedDict
from agents.meta_agent.models import (
    TaskSpec,
    AgentSpec,
    VerificationResult,
    TestResult,
    FounderReport,
    AuditEntry,
)


class MetaAgentState(TypedDict):
    """
    Full state passed between all 9 LangGraph nodes.
    Each node reads what it needs and writes its output back.
    should_stop is checked after every node — if True the graph
    skips remaining nodes and routes directly to return_report.
    """
    # Session identifiers
    task_id: str
    session_id: str

    # Raw input from founder
    founder_request: str

    # Node 1 output — parse_request
    task_spec: Optional[TaskSpec]

    # Node 2 output — validate_spec
    validation_errors: List[str]

    # Node 3 output — check_registry
    agent_already_exists: bool
    existing_agent_name: Optional[str]

    # Node 4 output — generate_spec
    agent_spec: Optional[AgentSpec]
    generated_spec_yaml: Optional[str]

    # Node 5 output — verify_spec
    verification_result: Optional[VerificationResult]

    # Node 6 output — generate_code
    generated_code: Optional[str]
    generated_config: Optional[str]
    code_file_path: Optional[str]
    config_file_path: Optional[str]

    # Node 7 output — run_tests
    test_result: Optional[TestResult]

    # Node 8 output — register_agent
    registered_agent_id: Optional[str]

    # Node 9 output — return_report
    founder_report: Optional[FounderReport]

    # Audit trail — appended by every node
    audit_entries: List[AuditEntry]

    # Token tracking — incremented by every AI call
    total_tokens_used: int

    # Error tracking
    current_error: Optional[str]

    # Kill switch — any node sets this to True on failure
    # Graph checks this after every node and routes to return_report
    should_stop: bool
