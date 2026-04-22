"""
元芯智能 AgentCore — 主 HTTP API。

集中注册业务路由与认证、支付、分析等子模块；具体端点随版本迭代扩展。
"""

from __future__ import annotations
import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
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
from agents.meta_agent.validation_gates import run_all_gates, get_gate_summary
from agents.meta_agent.architecture_invariants import check_invariants, get_invariant_list, VALID_DEPARTMENTS

load_dotenv()
import os
# Ensure critical env vars have defaults for production startup
if not os.getenv("PRIMARY_MODEL"):
    os.environ["PRIMARY_MODEL"] = "claude-sonnet-4-6"
if not os.getenv("DAILY_TOKEN_BUDGET"):
    os.environ["DAILY_TOKEN_BUDGET"] = "50000"
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
from agents.meta_agent.tools import router as tools_router
from agents.meta_agent.memory_system import router as memory_router, list_knowledge_documents
from agents.meta_agent.auth_extended import router as auth_extended_router
from agents.meta_agent.monitoring import router as monitoring_router
from agents.meta_agent.leaderboard import router as leaderboard_router
from agents.meta_agent.usage import router as usage_router
from agents.meta_agent.notifications import send_welcome_email, send_agent_created_email
from agents.meta_agent.plan_enforcement import (
    PLAN_LIMITS,
    enforce_agent_limit,
    enforce_daily_tokens_allowance,
    enforce_plan_feature,
    feature_access_map,
    get_plan_limits,
    load_user as pe_load_user,
    parse_bearer_email,
    resolve_scoped_user_email,
    require_feature,
)

from agents.meta_agent.auth import (
    load_users,
    save_user,
    save_users,
    get_user,
    create_user,
    verify_password,
    hash_password,
    make_token,
    register_user,
    login_user,
    get_user_by_token,
)
from agents.meta_agent import payment_cn


@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager."""
    # Startup
    try:
        from agents.meta_agent.models import init_db

        await init_db()
    except Exception:
        pass
    yield
    # Shutdown (optional cleanup)


app = FastAPI(
    title="元芯智能 AgentCore API",
    description="元芯智能体操作系统",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(analytics_router)
app.include_router(support_router)
app.include_router(clones_router)
app.include_router(workflows_router)
app.include_router(apikeys_router)
app.include_router(userkeys_router)
app.include_router(billing_router)
app.include_router(usage_router)
app.include_router(admin_router)
app.include_router(notifications_router)
app.include_router(templates_router)
app.include_router(tools_router)
app.include_router(memory_router)


@app.get(
    "/memory",
    dependencies=[Depends(require_feature("memory_knowledge"))],
    tags=["memory"],
)
def memory_catalog_no_trailing_slash(authorization: str | None = Header(None)) -> dict:
    """与 GET /memory/ 相同，便于前端直接请求 /memory。"""
    return list_knowledge_documents(authorization)
app.include_router(auth_extended_router)
app.include_router(monitoring_router)
app.include_router(leaderboard_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
        ).split(",")
        if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateAgentRequest(BaseModel):
    request: str
    user_email: str | None = None


class CreateAgentResponse(BaseModel):
    task_id: str
    status: str
    summary: str
    agent_name: str
    total_tokens_used: int
    errors: list[str]
    rollback_command: str


@app.get("/agents/invariants")
def list_invariants() -> dict:
    """Return all 25 architecture invariants."""
    return {"invariants": get_invariant_list(), "total": 25}


class RootInfo(BaseModel):
    """根路径 JSON 结构。"""

    message: str
    docs: str
    health: str


@app.get("/", response_model=RootInfo, tags=["系统"])
def root() -> RootInfo:
    """根路径说明。"""
    return RootInfo(
        message="元芯智能 AgentCore API",
        docs="/docs",
        health="/health",
    )


@app.get("/health")
def health_check() -> dict:
    dashboard = get_factory_dashboard()
    daily_tokens = get_daily_usage()
    drift = get_drift_status()
    all_alerts = dashboard["alerts"] + drift["alerts"]
    overall_status = "alert" if all_alerts else "healthy"
    return {
        "status": overall_status,
        "service": "元芯智能 AgentCore",
        "data_location": "中国境内",
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
def create_agent(
    body: CreateAgentRequest,
    authorization: str | None = Header(None),
) -> CreateAgentResponse:
    if not body.request or len(body.request.strip()) < 10:
        raise HTTPException(status_code=400, detail="描述至少 10 个字符。")
    user_email = resolve_scoped_user_email(body.user_email, authorization)
    enforce_agent_limit(user_email)
    enforce_daily_tokens_allowance(user_email, 10_000)

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


@app.get("/audit", dependencies=[Depends(require_feature("audit_log"))])
def get_audit_log(limit: int = 50) -> dict:
    entries = read_all_entries(limit=limit)
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}


@app.get("/agents/audit/logs", dependencies=[Depends(require_feature("audit_log"))])
def get_agents_audit_alias(limit: int = 50) -> dict:
    """与 /audit 一致，字段名 logs 便于前端统一客户端。"""
    entries = read_all_entries(limit=limit)
    return {"logs": [e.model_dump() for e in entries], "count": len(entries)}


@app.get("/metrics")
def get_metrics() -> dict:
    daily = int(os.getenv("DAILY_TOKEN_BUDGET", "50000"))
    used = get_daily_usage()
    return {
        "daily_tokens_used": used,
        "daily_budget": daily,
        "budget_remaining": max(0, daily - used),
        "budget_ok": is_within_daily_budget(),
    }


class RunTaskRequest(BaseModel):
    task: str


@app.post("/agents/{agent_name}/run")
def run_agent_task(
    agent_name: str,
    body: RunTaskRequest,
    authorization: str | None = Header(None),
) -> dict:
    if not body.task or len(body.task.strip()) < 5:
        raise HTTPException(status_code=400, detail="任务描述至少 5 个字符。")
    user_email = parse_bearer_email(authorization)
    if not user_email:
        raise HTTPException(
            status_code=401,
            detail="执行任务需要先登录，请在请求头携带 Authorization: Bearer 令牌。",
        )
    enforce_daily_tokens_allowance(user_email, 10_000)
    if not rate_limiter.is_allowed("founder"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")
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


@app.get("/agents/audit", dependencies=[Depends(require_feature("audit_log"))])
def audit_agents() -> dict:
    return audit_all_agents()


@app.get("/agents/{agent_name}/validate")
def validate_agent(agent_name: str) -> dict:
    """Run all 10 validation gates against a single agent spec."""
    agent = get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found: " + agent_name)
    return run_all_gates(agent)


@app.get("/agents/{agent_name}/validate/summary")
def validate_agent_summary(agent_name: str) -> dict:
    """Return quick validation summary (no gate details) for an agent."""
    agent = get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found: " + agent_name)
    return get_gate_summary(agent)


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
def set_budget(
    body: BudgetConfig,
    authorization: str | None = Header(None),
) -> dict:
    # Require owner-level auth before touching .env
    from agents.meta_agent.plan_enforcement import parse_bearer_email, load_user as _load_user
    email = parse_bearer_email(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="需要登录")
    user = _load_user(email)
    if not user or not (user.get("is_owner") or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="仅管理员可修改预算")
    if body.daily_budget < 0 or body.daily_budget > 10_000_000:
        raise HTTPException(status_code=400, detail="预算值超出合法范围")
    env_path = ".env"
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("DAILY_TOKEN_BUDGET="):
            new_lines.append(f"DAILY_TOKEN_BUDGET={body.daily_budget}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"DAILY_TOKEN_BUDGET={body.daily_budget}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.environ["DAILY_TOKEN_BUDGET"] = str(body.daily_budget)
    return {"status": "SUCCESS", "daily_budget": body.daily_budget}

@app.get("/system/budget")
def get_budget() -> dict:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    budget = int(os.getenv("DAILY_TOKEN_BUDGET", "50000"))
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
    captcha_answer: int | None = None
    captcha_expected: int | None = None


class ForgotPasswordBody(BaseModel):
    email: str


@app.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordBody) -> dict:
    email = body.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")
    return {"success": True, "message": "如果邮箱已注册，重置链接将发送至您的邮箱"}


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
    if body.captcha_expected is not None and body.captcha_answer is not None:
        if body.captcha_answer != body.captcha_expected:
            raise HTTPException(status_code=400, detail="Incorrect captcha answer.")
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    result, error = login_user(body.email, body.password, ip, ua)
    if error:
        raise HTTPException(status_code=401, detail=error)
    u = result["user"]
    tok = result["token"]
    limits = get_plan_limits(u.get("plan", "free"))
    return {
        "status": "SUCCESS",
        "token": tok,
        "access_token": tok,
        "token_type": "Bearer",
        "user": u,
        "plan": u.get("plan", "free"),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "is_admin": bool(u.get("is_admin", False)),
        "is_owner": bool(u.get("is_owner", False)),
        "daily_token_limit": int(limits["daily_tokens"]),
        "tokens_used_today": int(u.get("daily_tokens_used", 0)),
    }

@app.get("/auth/me")
def get_me(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或缺少令牌。")
    token = authorization.replace("Bearer ", "")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期，请重新登录。")
    limits = get_plan_limits(user.get("plan", "free"))
    plan = user.get("plan", "free")
    return {
        "user": {k: v for k, v in user.items() if k != "password_hash"},
        "plan_limits": limits,
        "daily_tokens_used": user.get("daily_tokens_used", 0),
        "daily_token_limit": limits["daily_tokens"],
        "feature_access": feature_access_map(plan),
        "is_admin": bool(user.get("is_admin", False)),
        "is_owner": bool(user.get("is_owner", False)),
    }

@app.get("/plans")
def get_plans() -> dict:
    return {"plans": PLAN_LIMITS}


@app.post("/payment/wechat/create")
def payment_wechat_create(
    body: payment_cn.WechatCreateRequest,
    authorization: str | None = Header(None),
) -> dict:
    """创建微信 Native 支付订单，返回二维码链接 code_url。"""
    try:
        scoped_email = resolve_scoped_user_email(body.user_email, authorization)
        payload = body.model_copy(update={"user_email": scoped_email})
        return payment_cn.wechat_native_create(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建微信支付失败：{exc!s}") from exc


@app.post("/payment/alipay/create")
def payment_alipay_create(
    body: payment_cn.AlipayCreateRequest,
    authorization: str | None = Header(None),
) -> dict:
    """创建支付宝当面付预下单，返回 qr_code 内容（code_url 字段与微信对齐）。"""
    try:
        scoped_email = resolve_scoped_user_email(body.user_email, authorization)
        payload = body.model_copy(update={"user_email": scoped_email})
        return payment_cn.alipay_precreate(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建支付宝订单失败：{exc!s}") from exc


@app.post("/payment/wechat/notify")
async def payment_wechat_notify(request: Request) -> dict:
    """微信支付异步通知。"""
    try:
        raw = await request.body()
        data = json.loads(raw.decode("utf-8"))
        return payment_cn.wechat_handle_notify(data)
    except Exception as exc:
        return {"code": "FAIL", "message": f"处理通知异常：{exc!s}"}


@app.post("/payment/alipay/notify")
async def payment_alipay_notify(request: Request) -> PlainTextResponse:
    """支付宝异步通知（返回纯文本 success/fail）。"""
    try:
        form = await request.form()
        form_dict = {str(k): str(v) for k, v in form.multi_items()}
        text = payment_cn.alipay_handle_notify(form_dict)
        return PlainTextResponse(content=text, media_type="text/plain")
    except Exception:
        return PlainTextResponse(content="fail", media_type="text/plain")


@app.get("/payment/status/{order_id}")
def payment_order_status(order_id: str) -> dict:
    """按内部 order_id 查询支付状态（微信会主动向渠道查询 trade_state）。"""
    try:
        return payment_cn.payment_status(order_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询订单失败：{exc!s}") from exc


@app.get("/payment/config")
def payment_config_cn() -> dict:
    """境内支付能力说明（与 /payments/config 互补）。"""
    cfg = get_payment_config()
    cfg["methods"] = ["wechat", "alipay"]
    cfg["currency"] = "CNY"
    cfg["plans_display"] = {
        "pro": {"monthly": 199, "yearly": 1680},
        "business": {"monthly": 599, "yearly": 4990},
    }
    cfg["note"] = "企业版请联系销售获取定制报价；标价单位：元人民币/月（年付为示意打包价）。"
    return cfg


class CheckoutRequest(BaseModel):
    plan: str
    user_email: str | None = None

@app.post("/payments/checkout")
def create_checkout(
    body: CheckoutRequest,
    request: Request,
    authorization: str | None = Header(None),
) -> dict:
    user_email = resolve_scoped_user_email(body.user_email, authorization)
    success_url = "http://localhost:3000/payment/success"
    cancel_url = "http://localhost:3000/login"
    session, error = create_checkout_session(user_email, body.plan, success_url, cancel_url)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if session is None:
        raise HTTPException(status_code=400, detail="无法创建境外结账会话，请改用微信支付或支付宝。")
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
def manual_upgrade(body: CheckoutRequest, authorization: str | None = Header(None)) -> dict:
    user_email = resolve_scoped_user_email(body.user_email, authorization)
    ok, msg = upgrade_user_plan(user_email, body.plan)
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

@app.get("/affiliate/stats")
def affiliate_stats_me(authorization: str | None = Header(None)) -> dict:
    """当前登录用户的推广统计（GET /affiliate/stats）。"""
    email = parse_bearer_email(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="未登录或缺少令牌。")
    enforce_plan_feature(email, "referral")
    user = pe_load_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在。")
    if get_affiliate_stats(email) is None:
        create_affiliate(email, user.get("name", email.split("@")[0]))
    stats = get_affiliate_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="未找到该推广账户。")
    summary = stats.get("summary") or {}
    return {
        "affiliate": stats.get("affiliate"),
        "referrals": stats.get("referrals") or [],
        "commission_rate": 15,
        "summary": summary,
    }


@app.get("/affiliate/{email}/stats")
def affiliate_stats(email: str, authorization: str = Header(default="")) -> dict:
    scoped_email = resolve_scoped_user_email(email, authorization)
    stats = get_affiliate_stats(scoped_email)
    if not stats:
        raise HTTPException(status_code=404, detail="未找到该推广账户。")
    return stats

@app.post("/affiliate/referral")
def track_referral(body: ReferralRequest) -> dict:
    ok, result = record_referral(body.affiliate_code, body.referred_email, body.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "SUCCESS", "referral": result}
