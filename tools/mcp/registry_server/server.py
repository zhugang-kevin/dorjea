"""
server.py — Registry MCP server for agent registry operations.
Runs as a separate process on port 8002.
FastMCP 3.x API.
"""
from __future__ import annotations
import os
import json
from fastmcp import FastMCP
from agents.meta_agent.registry import (
    agent_exists,
    register_agent,
    get_agent,
    list_agents,
    update_agent_status,
)

mcp = FastMCP("dorjea-registry")


@mcp.tool()
def check_duplicate(agent_name: str) -> str:
    """
    Check if an agent name already exists in the registry.
    Returns 'true' or 'false' as string.
    """
    try:
        return str(agent_exists(agent_name)).lower()
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def get_agent_by_name(agent_name: str) -> str:
    """
    Get full details for an agent by name.
    Returns JSON string of agent data or error message.
    """
    try:
        agent = get_agent(agent_name)
        if not agent:
            return f"ERROR: Agent '{agent_name}' not found."
        return json.dumps(agent)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def list_all_agents(status: str = "active") -> str:
    """
    List all agents with the given status.
    Returns JSON array of agent records.
    """
    try:
        agents = list_agents(status=status)
        return json.dumps(agents)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def update_status(agent_name: str, status: str) -> str:
    """
    Update the status of an agent in the registry.
    Valid statuses: active, idle, frozen, requires_review, archived.
    Returns OK or error message.
    """
    try:
        success = update_agent_status(agent_name, status)
        if success:
            return f"OK: Agent '{agent_name}' status updated to '{status}'"
        return f"ERROR: Failed to update status for '{agent_name}'"
    except Exception as e:
        return f"ERROR: {e}"


if __name__ == "__main__":
    port = int(os.getenv("REGISTRY_MCP_PORT", "8002"))
    print(f"Starting Registry MCP Server on port {port}...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=port)
