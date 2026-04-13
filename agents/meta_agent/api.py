from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from agents.meta_agent.graph import meta_agent_graph
from agents.meta_agent.registry import list_agents, get_agent
from agents.meta_agent.audit_logger import read_all_entries
from self_defence.injection_detector import is_safe
from self_defence.rate_limiter import rate_limiter
from self_monitoring.health_monitor import get_factory_dashboard
from self_token.budget_manager import get_daily_usage, is_within_daily_budget
from self_monitoring.drift_detector import get_drift_status
from self_monitoring.agent_performance import get_performance_summary
from agents.runtime.agent_runtime import runtime
from agents.meta_agent.task_gateway import gateway

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
    request: str


class CreateAgentResponse(BaseModel):
    task_id: str
    status: str
    summary: str
    agent_name: str
    total_tokens_used: int
    errors: list[str]
    rollback_command: str


@app.get("/health")
def health_check() -> dict:
    dashboard = get_factory_dashboard()
    daily_tokens = get_daily_usage()
    drift = get_drift_status()
    all_alerts = dashboard["alerts"] + drift["alerts"]
    overall_status = "alert" if all_alerts else "healthy"
    return {
        "status": overall_status,
        "service": "Dorjea AI Factory",
        "system": dashboard["system"],
        "alerts": all_alerts,
        "daily_tokens_used": daily_tokens,
        "daily_budget_ok": is_within_daily_budget(),
        "drift": {
            "health_score": drift["health_score"],
            "drift_detected": drift["drift_detected"],
            "status": drift["status"],
        },
    }


@app.post("/agents/create", response_model=CreateAgentResponse)
def create_agent(body: CreateAgentRequest) -> CreateAgentResponse:
    if not body.request or len(body.request.strip()) < 10:
        raise HTTPException(status_code=400, detail="Request must be at least 10 characters.")

    task_envelope, errors = gateway.validate_and_admit(
        body.request, source="founder"
    )
    if errors:
        raise HTTPException(status_code=400, detail=" | ".join(errors))

    task_id = task_envelope["task_id"]
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
        raise HTTPException(status_code=500, detail="Graph execution failed: " + str(e))

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
    agents = list_agents(status=status)
    return {"agents": agents, "count": len(agents)}


@app.get("/agents/{agent_name}")
def get_agent_by_name(agent_name: str) -> dict:
    agent = get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found: " + agent_name)
    return agent


@app.get("/audit")
def get_audit_log(limit: int = 50) -> dict:
    entries = read_all_entries(limit=limit)
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}


@app.get("/metrics")
def get_metrics() -> dict:
    return {
        "daily_tokens_used": get_daily_usage(),
        "daily_budget": 100000,
        "budget_remaining": 100000 - get_daily_usage(),
        "budget_ok": is_within_daily_budget(),
    }


class RunTaskRequest(BaseModel):
    task: str


@app.post("/agents/{agent_name}/run")
def run_agent_task(agent_name: str, body: RunTaskRequest) -> dict:
    if not body.task or len(body.task.strip()) < 5:
        raise HTTPException(status_code=400, detail="Task must be at least 5 characters.")
    if not rate_limiter.is_allowed("founder"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    safe, reason = is_safe(body.task, agent_id="founder")
    if not safe:
        raise HTTPException(status_code=400, detail="Task blocked: " + reason)
    result = runtime.run_task(agent_name, body.task)
    if result["status"] == "FAILED":
        raise HTTPException(status_code=400, detail=result.get("error", "Task failed"))
    return result

@app.get("/performance")
def get_performance() -> dict:
    return get_performance_summary()