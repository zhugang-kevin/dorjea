"""
graph.py — Main LangGraph stateful graph for the Meta-Agent.
Wires all 9 nodes together with conditional edges.
Uses LangGraph 1.1.x StateGraph API with memory checkpointing.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.meta_agent.state import MetaAgentState
from agents.meta_agent.nodes import (
    parse_request,
    validate_spec,
    check_registry,
    generate_spec,
    verify_spec,
    generate_code,
    run_tests,
    register_agent,
    return_report,
)


def _should_stop(state: MetaAgentState) -> str:
    """
    Conditional edge function checked after every node.
    If should_stop is True, route directly to return_report.
    Otherwise continue to the next node in sequence.
    """
    if state.get("should_stop"):
        return "return_report"
    return "continue"


def build_graph() -> StateGraph:
    """
    Build and compile the Meta-Agent LangGraph workflow.
    Returns a compiled graph ready to invoke.
    """
    builder = StateGraph(MetaAgentState)

    # Add all 9 nodes
    builder.add_node("parse_request", parse_request)
    builder.add_node("validate_spec", validate_spec)
    builder.add_node("check_registry", check_registry)
    builder.add_node("generate_spec", generate_spec)
    builder.add_node("verify_spec", verify_spec)
    builder.add_node("generate_code", generate_code)
    builder.add_node("run_tests", run_tests)
    builder.add_node("register_agent", register_agent)
    builder.add_node("return_report", return_report)

    # Entry point
    builder.set_entry_point("parse_request")

    # Conditional edges after each node — stop or continue
    builder.add_conditional_edges(
        "parse_request",
        _should_stop,
        {"return_report": "return_report", "continue": "validate_spec"},
    )
    builder.add_conditional_edges(
        "validate_spec",
        _should_stop,
        {"return_report": "return_report", "continue": "check_registry"},
    )
    builder.add_conditional_edges(
        "check_registry",
        _should_stop,
        {"return_report": "return_report", "continue": "generate_spec"},
    )
    builder.add_conditional_edges(
        "generate_spec",
        _should_stop,
        {"return_report": "return_report", "continue": "verify_spec"},
    )
    builder.add_conditional_edges(
        "verify_spec",
        _should_stop,
        {"return_report": "return_report", "continue": "generate_code"},
    )
    builder.add_conditional_edges(
        "generate_code",
        _should_stop,
        {"return_report": "return_report", "continue": "run_tests"},
    )
    builder.add_conditional_edges(
        "run_tests",
        _should_stop,
        {"return_report": "return_report", "continue": "register_agent"},
    )
    builder.add_conditional_edges(
        "register_agent",
        _should_stop,
        {"return_report": "return_report", "continue": "return_report"},
    )

    # return_report always ends the graph
    builder.add_edge("return_report", END)

    # Compile with memory checkpointing
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


# Single compiled graph instance used by the API
meta_agent_graph = build_graph()
