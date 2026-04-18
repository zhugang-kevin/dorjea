from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException, Request, Header
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
from agents.meta_agent.version_checker import check_all_versions
from agents.meta_agent.agent_auditor import audit_all_agents
from agents.meta_agent.lifecycle_manager import transition_agent, get_lifecycle_summary, get_lifecycle_history
from agents.meta_agent.communication_protocol import send_message, get_messages
from agents.meta_agent.knowledge_consistency import get_knowledge_summary, check_consistency
from self_monitoring.agent_performance import get_performance_summary
from agents.runtime.agent_runtime import runtime
from agents.meta_agent.task_gateway import gateway
from agents.meta_agent.task_integrity import run_task_integrity_check, complete_task_record

load_dotenv()
import os
# Ensure critical env vars have defaults for production startup
if not os.getenv("PRIMARY_MODEL"):
    os.environ["PRIMARY_MODEL"] = "claude-sonnet-4-6"
if not os.getenv("DAILY_TOKEN_BUDGET"):
    os.environ["DAILY_TOKEN_BUDGET"] = "100000"
if not os.getenv("JWT_SECRET_KEY"):
    import secrets
    os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)

from agents.meta_agent.payments import create_checkout_session, handle_webhook, get_payment_config, upgrade_user_plan
from agents.meta_agent.affiliate import create_affiliate, get_affiliate_stats, record_referral
from agents.meta_agent.analytics import router as analytics_router
from agents.meta_agent.support import router as support_router
from agents.meta_agent.clones import router as clones_router
from agents.meta_agent.workflows import router as workflows_router
from agents.meta_agent.api_keys import router as apikeys_router
from agents.meta_agent.user_keys import router as userkeys_router
from agents.meta_agent.billing import router as billing_router
from agents.meta_agent.admin import router as admin_router
from agents.meta_agent.notifications import router as notifications_router
from agents.meta_agent.templates import router as templates_router
from agents.meta_agent.notifications import send_welcome_email, send_agent_created_email
from agents.meta_agent.plan_enforcement import enforce_agent_limit, enforce_clone_limit

from agents.meta_agent.auth import (
    register_user, login_user, get_user_by_token,
    get_plan_limits, PLAN_LIMITS
)

app = FastAPI(
    title="Dorjea AI Factory",
    description="Meta-Agent API — submit plain-English requests to create AI agents.",
    version="1.0.0",
)


app.include_router(analytics_router)
app.include_router(support_router)
app.include_router(clones_router)
app.include_router(workflows_router)
app.include_router(apikeys_router)
app.include_router(userkeys_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(notifications_router)
app.include_router(templates_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    # Plan enforcement - check agent limit
    try:
        user_email = getattr(body, "user_email", None)
        if user_email:
            enforce_agent_limit(user_email)
    except HTTPException:
        raise
    except Exception:
        pass

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

    integrity_ok, integrity_errors = run_task_integrity_check(task_envelope)
    if not integrity_ok:
        raise HTTPException(status_code=400, detail=" | ".join(integrity_errors))

    try:
        final_state = meta_agent_graph.invoke(initial_state, config=config)
    except Exception as e:
        complete_task_record(task_id, "failed", output_preview=str(e))
        raise HTTPException(status_code=500, detail="Graph execution failed: " + str(e))

    report = final_state.get("founder_report")
    if not report:
        complete_task_record(task_id, "failed", output_preview="No report returned")
        raise HTTPException(status_code=500, detail="No report returned from graph.")

    complete_task_record(
        task_id=task_id,
        status=report.status.lower(),
        tokens_used=report.total_tokens_used,
        output_preview=report.summary,
    )

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

@app.get("/system/versions")
def get_versions() -> dict:
    return check_all_versions()


@app.get("/agents/audit")
def audit_agents() -> dict:
    return audit_all_agents()


@app.get("/agents/lifecycle")
def lifecycle_summary() -> dict:
    return get_lifecycle_summary()

@app.get("/agents/{agent_name}/lifecycle")
def agent_lifecycle_history(agent_name: str) -> dict:
    return {"agent": agent_name, "history": get_lifecycle_history(agent_name)}

@app.post("/agents/{agent_name}/deploy")
def deploy_agent_endpoint(agent_name: str) -> dict:
    ok, msg = transition_agent(agent_name, "deployed", "Deployed via API")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}

@app.post("/agents/{agent_name}/retire")
def retire_agent_endpoint(agent_name: str) -> dict:
    ok, msg = transition_agent(agent_name, "retired", "Retired via API")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}


@app.get("/system/knowledge")
def knowledge_summary() -> dict:
    return get_knowledge_summary()

@app.get("/system/knowledge/consistency")
def knowledge_consistency() -> dict:
    return check_consistency()


class BudgetConfig(BaseModel):
    daily_budget: int

@app.post("/system/budget")
def set_budget(body: BudgetConfig) -> dict:
    import os
    env_path = ".env"
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("DAILY_TOKEN_BUDGET="):
            new_lines.append("DAILY_TOKEN_BUDGET=" + str(body.daily_budget) + chr(10))
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append("DAILY_TOKEN_BUDGET=" + str(body.daily_budget) + chr(10))
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.environ["DAILY_TOKEN_BUDGET"] = str(body.daily_budget)
    return {"status": "SUCCESS", "daily_budget": body.daily_budget}

@app.get("/system/budget")
def get_budget() -> dict:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    budget = int(os.getenv("DAILY_TOKEN_BUDGET", "100000"))
    used = get_daily_usage()
    return {
        "daily_budget": budget,
        "tokens_used": used,
        "tokens_remaining": max(0, budget - used),
        "usage_percent": round(used / budget * 100, 1) if budget > 0 else 0,
    }


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    lang: str = "en"

class LoginRequest(BaseModel):
    email: str
    password: str
    captcha_answer: int
    captcha_expected: int

@app.post("/auth/register")
def register(body: RegisterRequest, request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    user, error = register_user(body.email, body.password, body.name, ip, ua, body.lang)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "message": "Registration successful. Please login."}

@app.post("/auth/login")
def login(body: LoginRequest, request: Request) -> dict:
    if body.captcha_answer != body.captcha_expected:
        raise HTTPException(status_code=400, detail="Incorrect captcha answer.")
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    result, error = login_user(body.email, body.password, ip, ua)
    if error:
        raise HTTPException(status_code=401, detail=error)
    return {"status": "SUCCESS", "token": result["token"], "user": result["user"]}

@app.get("/auth/me")
def get_me(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    limits = get_plan_limits(user.get("plan", "free"))
    return {
        "user": {k: v for k, v in user.items() if k != "password_hash"},
        "plan_limits": limits,
        "daily_tokens_used": user.get("daily_tokens_used", 0),
        "daily_token_limit": limits["daily_tokens"],
    }

@app.get("/plans")
def get_plans() -> dict:
    return {"plans": PLAN_LIMITS}


class CheckoutRequest(BaseModel):
    plan: str
    user_email: str

@app.post("/payments/checkout")
def create_checkout(body: CheckoutRequest, request: Request) -> dict:
    success_url = "http://localhost:3000/payment/success"
    cancel_url = "http://localhost:3000/login"
    session, error = create_checkout_session(body.user_email, body.plan, success_url, cancel_url)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "checkout_url": session.url, "session_id": session.id}

@app.post("/payments/webhook")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    ok, msg = handle_webhook(payload, sig_header)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "OK"}

@app.post("/payments/upgrade")
def manual_upgrade(body: CheckoutRequest) -> dict:
    ok, msg = upgrade_user_plan(body.user_email, body.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}

@app.get("/payments/config")
def payment_config() -> dict:
    return get_payment_config()


class AffiliateRequest(BaseModel):
    email: str
    name: str

class ReferralRequest(BaseModel):
    affiliate_code: str
    referred_email: str
    plan: str

@app.post("/affiliate/register")
def register_affiliate(body: AffiliateRequest) -> dict:
    affiliate, error = create_affiliate(body.email, body.name)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "affiliate": affiliate}

@app.get("/affiliate/{email}/stats")
def affiliate_stats(email: str, authorization: str = Header(default="")) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    stats = get_affiliate_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return stats

@app.post("/affiliate/referral")
def track_referral(body: ReferralRequest) -> dict:
    ok, result = record_referral(body.affiliate_code, body.referred_email, body.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "SUCCESS", "referral": result}


class AffiliateRequest(BaseModel):
    email: str
    name: str

class ReferralRequest(BaseModel):
    affiliate_code: str
    referred_email: str
    plan: str

@app.post("/affiliate/register")
def register_affiliate(body: AffiliateRequest) -> dict:
    affiliate, error = create_affiliate(body.email, body.name)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "affiliate": affiliate}

@app.get("/affiliate/{email}/stats")
def affiliate_stats(email: str, authorization: str = Header(default="")) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    stats = get_affiliate_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return stats

@app.post("/affiliate/referral")
def track_referral(body: ReferralRequest) -> dict:
    ok, result = record_referral(body.affiliate_code, body.referred_email, body.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "SUCCESS", "referral": result}
