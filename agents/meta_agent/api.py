"""
api.py — FastAPI application for the Dorjea AI Factory Meta-Agent.
All founder requests enter through this file.
Start with: uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port 8000
"""
from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from agents.meta_agent.graph import meta_agent_graph
from agents.meta_agent.registry import list_agents, get_agent
from agents.meta_agent.audit_logger import read_all_entries

load_dotenv()

app = FastAPI(
    title="Dorjea AI Factory",
    description="Meta-Agent API — submit plain-English requests to create AI agents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateAgentRequest(BaseModel):
    """Request body for POST /agents/create."""
    request: str


class CreateAgentResponse(BaseModel):
    """Response body for POST /agents/create."""
    task_id: str
    status: str
    summary: str
    agent_name: str
    total_tokens_used: int
    errors: list[str]
    rollback_command: str


@app.get("/health")
def health_check() -> dict:
    """
    Health check endpoint.
    Returns 200 if the API is running.
    """
    return {"status": "ok", "service": "Dorjea AI Factory"}


@app.post("/agents/create", response_model=CreateAgentResponse)
def create_agent(body: CreateAgentRequest) -> CreateAgentResponse:
    """
    Submit a plain-English request to create a new AI agent.
    The Meta-Agent handles parsing, validation, generation, and registration.
    Returns a FounderReport with full status and rollback command.
    """
    if not body.request or len(body.request.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Request must be at least 10 characters long."
        )

    task_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    initial_state = {
        "task_id": task_id,
        "session_id": session_id,
        "founder_request": body.request.strip(),
        "task_spec": None,
        "validation_errors": [],
        "agent_already_exists": False,
        "existing_agent_name": None,
        "agent_spec": None,
        "generated_spec_yaml": None,
        "verification_result": None,
        "generated_code": None,
        "generated_config": None,
        "code_file_path": None,
        "config_file_path": None,
        "test_result": None,
        "registered_agent_id": None,
        "founder_report": None,
        "audit_entries": [],
        "total_tokens_used": 0,
        "current_error": None,
        "should_stop": False,
    }

    config = {"configurable": {"thread_id": task_id}}

    try:
        final_state = meta_agent_graph.invoke(initial_state, config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

    report = final_state.get("founder_report")
    if not report:
        raise HTTPException(status_code=500, detail="No report returned from graph.")

    return CreateAgentResponse(
        task_id=report.task_id,
        status=report.status,
        summary=report.summary,
        agent_name=report.agent_name,
        total_tokens_used=report.total_tokens_used,
        errors=report.errors,
        rollback_command=report.rollback_command,
    )


@app.get("/agents")
def list_all_agents(status: str = "active") -> dict:
    """
    List all registered agents filtered by status.
    Default status is active.
    """
    agents = list_agents(status=status)
    return {"agents": agents, "count": len(agents)}


@app.get("/agents/{agent_name}")
def get_agent_by_name(agent_name: str) -> dict:
    """
    Get full details for a single agent by name.
    Returns 404 if agent not found.
    """
    agent = get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")
    return agent


@app.get("/audit")
def get_audit_log(limit: int = 50) -> dict:
    """
    Return the last N audit log entries.
    Default is 50 entries.
    """
    entries = read_all_entries(limit=limit)
    return {
        "entries": [e.model_dump() for e in entries],
        "count": len(entries),
    }
