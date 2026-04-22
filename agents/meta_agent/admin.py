"""
超级管理员路由 — 元芯智能 AgentCore
需 OWNER JWT（可带 admin_ 前缀）或 ADMIN_SECRET_KEY。
保留 /overview、/user/* 等兼容接口；新增特权开户、批量生成、审计等。
"""

from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Depends, Request
from pydantic import BaseModel, field_validator

from agents.meta_agent.auth import (load_users, save_user, save_users, get_user, create_user, verify_password, hash_password, make_token)
from agents.meta_agent.plan_enforcement import (
    PLAN_LIMITS,
    PLAN_NAMES_CN,
    resolve_super_admin_actor,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

USERS_FILE = "memory/users.jsonl"
AGENTS_FILE = "memory/agents.jsonl"
BILLING_FILE = "memory/billing_history.jsonl"
TICKETS_FILE = "memory/support_tickets.jsonl"
AUDIT_FILE = "memory/audit_log.jsonl"
AUDIT_OWNER_FILE = Path("logs/admin_audit.jsonl")
TASKS_FILE = "memory/tasks.jsonl"

VALID_PLANS = ["free", "pro", "professional", "business", "enterprise"]
PLAN_PRICES = {"free": 0, "pro": 29, "professional": 29, "business": 99, "enterprise": 0, "owner": 0}


def verify_admin_access(authorization: str = Header(...)) -> str:
    return resolve_super_admin_actor(authorization)


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def rewrite_jsonl(path, data):
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")


def _norm_plan(p: str | None) -> str:
    x = (p or "free").lower().strip()
    if x == "pro":
        return "professional"
    return x


def _audit_owner_file(admin_email: str, action: str, target: str, detail: str) -> None:
    AUDIT_OWNER_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": str(uuid.uuid4()),
        "admin_email": admin_email,
        "action": action,
        "target": target,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(AUDIT_OWNER_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_admin_audit(action: str, actor: str, details: dict) -> None:
    parent = os.path.dirname(AUDIT_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    entry = {
        "logged_at": datetime.utcnow().isoformat(),
        "channel": "admin",
        "action": action,
        "actor": actor,
        "details": details,
    }
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    target = str(details.get("email") or details.get("user_email") or actor)
    _audit_owner_file(actor, action, target, json.dumps(details, ensure_ascii=False))


def _load_all_users_list() -> list[dict]:
    return load_jsonl(USERS_FILE)


def _save_users(users: list[dict]) -> None:
    os.makedirs(os.path.dirname(USERS_FILE) or ".", exist_ok=True)
    rewrite_jsonl(USERS_FILE, users)


def _build_overview() -> dict:
    users = load_jsonl(USERS_FILE)
    agents = load_jsonl(AGENTS_FILE)
    tickets = load_jsonl(TICKETS_FILE)
    billing = load_jsonl(BILLING_FILE)
    tasks = load_jsonl(TASKS_FILE)

    now = datetime.utcnow()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    def parse_dt(s):
        try:
            return datetime.fromisoformat(str(s).replace("Z", ""))
        except Exception:
            return datetime.min

    total_users = len(users)
    new_users_7d = len([u for u in users if parse_dt(u.get("created_at", "")) > last_7d])
    new_users_30d = len([u for u in users if parse_dt(u.get("created_at", "")) > last_30d])

    plan_counts = defaultdict(int)
    for u in users:
        plan_counts[u.get("plan", "free")] += 1

    mrr = sum(PLAN_PRICES.get(u.get("plan", "free"), 0) for u in users)
    active_users = len([u for u in users if parse_dt(u.get("last_login", "")) > last_7d])
    open_tickets = len([t for t in tickets if t.get("status") in ["open", "in_progress"]])
    urgent_tickets = len(
        [t for t in tickets if t.get("priority") == "urgent" and t.get("status") != "resolved"]
    )
    total_agents = len([a for a in agents if not a.get("deleted")])
    active_agents = len([a for a in agents if a.get("status") == "active"])

    users_by_day = defaultdict(int)
    for u in users:
        dt = parse_dt(u.get("created_at", ""))
        if dt > last_7d:
            users_by_day[dt.strftime("%Y-%m-%d")] += 1

    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    growth_chart = [{"date": d, "users": users_by_day.get(d, 0)} for d in days]

    return {
        "summary": {
            "total_users": total_users,
            "new_users_7d": new_users_7d,
            "new_users_30d": new_users_30d,
            "active_users_7d": active_users,
            "mrr": mrr,
            "arr": mrr * 12,
            "total_agents": total_agents,
            "active_agents": active_agents,
            "open_tickets": open_tickets,
            "urgent_tickets": urgent_tickets,
        },
        "plan_breakdown": dict(plan_counts),
        "growth_chart": growth_chart,
        "recent_users": sorted(users, key=lambda x: x.get("created_at", ""), reverse=True)[:10],
    }


def _owner_dashboard_stats(admin_email: str) -> dict:
    users = _load_all_users_list()
    keys = ["free", "pro", "professional", "business", "enterprise", "owner"]
    plan_dist = {p: 0 for p in keys}
    active_count = 0
    for u in users:
        p = (u.get("plan") or "free").lower()
        if p not in plan_dist:
            p = "free"
        plan_dist[p] = plan_dist.get(p, 0) + 1
        if not u.get("suspended", False):
            active_count += 1

    today_actions = 0
    if AUDIT_OWNER_FILE.exists():
        today = datetime.utcnow().strftime("%Y-%m-%d")
        try:
            with open(AUDIT_OWNER_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        if str(e.get("timestamp", "")).startswith(today):
                            today_actions += 1
                    except Exception:
                        continue
        except Exception:
            pass

    gen_count = sum(1 for u in users if u.get("generated_by_admin"))
    paid = sum(plan_dist.get(p, 0) for p in ["pro", "professional", "business", "enterprise"])

    return {
        "total_users": len(users),
        "active_users": active_count,
        "suspended_users": len(users) - active_count,
        "plan_distribution": plan_dist,
        "paid_users": paid,
        "free_users": plan_dist.get("free", 0),
        "today_actions": today_actions,
        "generated_accounts": gen_count,
        "system": {
            "name": os.getenv("SYSTEM_NAME", "元芯智能"),
            "domain": os.getenv("SYSTEM_DOMAIN", "agentcore.ai"),
            "admin_email": admin_email,
        },
    }


@router.get("/overview")
def admin_overview(_actor: str = Depends(verify_admin_access)):
    return _build_overview()


@router.get("/stats")
def admin_stats_dashboard(actor: str = Depends(verify_admin_access)):
    """新版管理台统计（与 /overview 不同结构）。"""
    em = actor if actor != "api_key" else os.getenv("OWNER_EMAIL", "api_key")
    return _owner_dashboard_stats(em)


@router.get("/legacy-stats")
def admin_legacy_stats_alias(_actor: str = Depends(verify_admin_access)):
    """旧版 /stats 与 overview 相同（兼容历史客户端）。"""
    return _build_overview()


@router.get("/audit-log")
def admin_audit_log(_actor: str = Depends(verify_admin_access), limit: int = 100):
    rows = load_jsonl(AUDIT_FILE)
    rows.sort(key=lambda x: x.get("logged_at", ""), reverse=True)
    cap = max(1, min(limit, 500))
    return {"entries": rows[:cap], "total": len(rows)}


@router.get("/audit-logs")
def admin_audit_logs_owner(
    _actor: str = Depends(verify_admin_access),
    page: int = 1,
    page_size: int = 50,
):
    logs = []
    if AUDIT_OWNER_FILE.exists():
        try:
            with open(AUDIT_OWNER_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line.strip()))
                    except Exception:
                        continue
        except Exception:
            pass
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    total = len(logs)
    start = max(0, (page - 1) * page_size)
    return {
        "logs": logs[start : start + page_size],
        "total": total,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size if page_size else 1,
    }


@router.get("/owner-info")
def admin_owner_info(actor: str = Depends(verify_admin_access)):
    admin_email = actor if actor != "api_key" else (os.getenv("OWNER_EMAIL") or "api_key")
    return {
        "email": admin_email,
        "role": "owner",
        "role_name": "系统所有者",
        "level": 99,
        "permissions": [
            "查看所有用户信息",
            "生成任意套餐的特权账户",
            "批量生成特权账户（最多50个）",
            "修改任意用户套餐",
            "设置用户专属折扣",
            "封禁/解封用户账户",
            "永久删除用户账户",
            "查看管理员操作审计日志",
            "访问所有系统功能（无任何限制）",
            "无Token数量限制",
            "无AI助手数量限制",
        ],
        "token_limit": "无限制",
        "agent_limit": "无限制",
        "features": "全部功能",
    }


@router.get("/users")
def list_all_users(
    _actor: str = Depends(verify_admin_access),
    plan: str | None = None,
    search: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
):
    users = _load_all_users_list()
    if plan and plan != "all":
        users = [u for u in users if u.get("plan") == plan]
    if search:
        s = search.lower()
        users = [
            u
            for u in users
            if s in u.get("email", "").lower() or s in u.get("name", "").lower()
        ]
    users.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    total = len(users)

    if page is not None and page_size is not None:
        start = max(0, (page - 1) * page_size)
        slice_u = users[start : start + page_size]
    else:
        slice_u = users
        page = 1
        page_size = total or 1

    formatted = []
    for u in slice_u:
        raw_plan = u.get("plan", "free")
        np = _norm_plan(raw_plan)
        lim = PLAN_LIMITS.get(np, PLAN_LIMITS["free"])
        formatted.append(
            {
                **{k: v for k, v in u.items() if k not in ["password_hash", "salt"]},
                "plan_name": PLAN_NAMES_CN.get(raw_plan, PLAN_NAMES_CN.get(np, "免费版")),
                "tokens_used_today": u.get("daily_tokens_used", 0),
                "daily_token_limit": lim.get("daily_tokens", 5000),
            }
        )

    return {
        "users": formatted,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 1,
    }


@router.get("/user/{email}")
def get_user_detail(email: str, _actor: str = Depends(verify_admin_access)):
    users = load_jsonl(USERS_FILE)
    user = next((u for u in users if u.get("email") == email), None)
    if not user:
        raise HTTPException(404, detail="User not found")
    agents = load_jsonl(AGENTS_FILE)
    user_agents = [a for a in agents if a.get("user_email") == email]
    tickets = load_jsonl(TICKETS_FILE)
    user_tickets = [t for t in tickets if t.get("user_email") == email]
    billing = load_jsonl(BILLING_FILE)
    user_billing = [b for b in billing if b.get("user_email") == email]
    safe_user = {k: v for k, v in user.items() if k not in ["password_hash", "salt"]}
    return {
        "user": safe_user,
        "agents": user_agents,
        "tickets": user_tickets,
        "billing": user_billing,
        "stats": {
            "total_agents": len(user_agents),
            "active_agents": len([a for a in user_agents if a.get("status") == "active"]),
            "total_tickets": len(user_tickets),
            "open_tickets": len([t for t in user_tickets if t.get("status") == "open"]),
        },
    }


# ---------- Pydantic ----------
class UpdateUserPlanRequest(BaseModel):
    email: str
    plan: str
    reason: Optional[str] = ""


class SuspendUserRequest(BaseModel):
    email: str
    suspended: bool
    reason: Optional[str] = ""


class OwnerSuspendRequest(BaseModel):
    user_email: str
    reason: str = ""


class SetPlanAliasRequest(BaseModel):
    user_email: str
    new_plan: str
    reason: str = ""
    expires_days: int = 0


class SetDiscountRequest(BaseModel):
    user_email: str
    discount_percent: float
    reason: str = ""


class CreateFreeUserRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    reason: str = ""


class GenerateAccountRequest(BaseModel):
    email: str
    name: str
    plan: str
    password: str = ""
    note: str = ""
    expires_days: int = 0

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_PLANS:
            raise ValueError(f"无效套餐，可选：{', '.join(VALID_PLANS)}")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.lower().strip()
        if "@" not in v:
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("expires_days")
    @classmethod
    def validate_expires(cls, v: int) -> int:
        if v < 0:
            raise ValueError("有效期不能为负数")
        return v


class BatchGenerateRequest(BaseModel):
    accounts: list[GenerateAccountRequest]

    @field_validator("accounts")
    @classmethod
    def validate_accounts(cls, v: list) -> list:
        if not v:
            raise ValueError("账户列表不能为空")
        if len(v) > 50:
            raise ValueError("单次最多生成50个账户")
        return v


def _generate_account_core(req: GenerateAccountRequest, admin_email: str) -> dict:
    users = _load_all_users_list()
    store_plan = req.plan
    if store_plan == "pro":
        store_plan = "professional"

    existing = next((u for u in users if u.get("email", "").lower() == req.email.lower()), None)
    if existing:
        for user in users:
            if user.get("email", "").lower() == req.email.lower():
                user["plan"] = store_plan
                user["note"] = req.note or user.get("note", "")
                user["updated_at"] = datetime.utcnow().isoformat()
                user["generated_by_admin"] = True
                if req.expires_days > 0:
                    user["expires_at"] = (datetime.utcnow() + timedelta(days=req.expires_days)).isoformat()
                break
        _save_users(users)
        _audit_owner_file(admin_email, "update_generated_account", req.email, f"更新为{store_plan}，{req.note}")
        append_admin_audit(
            "update_generated_account",
            admin_email,
            {"email": req.email, "plan": store_plan, "note": req.note},
        )
        return {
            "success": True,
            "action": "updated",
            "email": req.email,
            "plan": store_plan,
            "plan_name": PLAN_NAMES_CN.get(store_plan, store_plan),
            "message": f"账户已更新为{PLAN_NAMES_CN.get(store_plan, store_plan)}",
        }

    password = req.password or f"AgentCore@{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow().isoformat()
    expires_at = ""
    if req.expires_days > 0:
        expires_at = (datetime.utcnow() + timedelta(days=req.expires_days)).isoformat()

    new_user = {
        "id": str(uuid.uuid4()),
        "email": req.email.lower(),
        "name": req.name,
        "password_hash": hash_password(password),
        "plan": store_plan,
        "generated_by_admin": True,
        "generated_by": admin_email,
        "note": req.note,
        "suspended": False,
        "active": True,
        "discount_percent": 100,
        "daily_tokens_used": 0,
        "tokens_reset_date": datetime.utcnow().date().isoformat(),
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
        "is_admin": False,
        "is_owner": False,
        "login_count": 0,
        "device_fingerprints": [],
        "lang": "zh",
    }
    users.append(new_user)
    _save_users(users)
    _audit_owner_file(
        admin_email,
        "generate_account",
        req.email,
        f"生成{store_plan}，{req.note}，{req.expires_days}天",
    )
    append_admin_audit(
        "generate_account",
        admin_email,
        {"email": req.email, "plan": store_plan, "note": req.note},
    )
    return {
        "success": True,
        "action": "created",
        "email": req.email,
        "name": req.name,
        "plan": store_plan,
        "plan_name": PLAN_NAMES_CN.get(store_plan, store_plan),
        "password": password,
        "expires_at": expires_at or "永不过期",
        "message": f"{PLAN_NAMES_CN.get(store_plan, store_plan)}账户已生成",
        "warning": "密码仅显示一次，请立即记录！",
    }


@router.post("/generate-account")
def generate_account(req: GenerateAccountRequest, actor: str = Depends(verify_admin_access)):
    admin_email = actor if actor != "api_key" else "api_key"
    return _generate_account_core(req, admin_email)


@router.post("/batch-generate")
def batch_generate_accounts(req: BatchGenerateRequest, actor: str = Depends(verify_admin_access)):
    admin_email = actor if actor != "api_key" else "api_key"
    results = []
    ok, fail = 0, 0
    for account in req.accounts:
        try:
            r = _generate_account_core(account, admin_email)
            results.append(
                {
                    "email": account.email,
                    "status": "success",
                    "plan": r.get("plan"),
                    "password": r.get("password", "（已存在则未改密）"),
                    "message": r.get("message", ""),
                }
            )
            ok += 1
        except Exception as e:
            results.append({"email": account.email, "status": "failed", "error": str(e)})
            fail += 1
    _audit_owner_file(admin_email, "batch_generate", f"{len(req.accounts)}", f"成功{ok}失败{fail}")
    return {
        "success": True,
        "total": len(req.accounts),
        "success_count": ok,
        "fail_count": fail,
        "results": results,
    }


@router.post("/users/create-free")
def admin_create_free_user(
    req: CreateFreeUserRequest,
    request: Request,
    actor: str = Depends(verify_admin_access),
):
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    display_name = (req.name or "").strip() or req.email.split("@")[0]
    user, err = register_user(req.email, req.password, display_name, ip, ua, "zh")
    if err:
        raise HTTPException(status_code=400, detail=err)
    append_admin_audit(
        "create_free_user",
        actor,
        {"email": req.email, "reason": req.reason, "name": display_name},
    )
    safe = {k: v for k, v in user.items() if k != "password_hash"}
    return {"success": True, "message": "账户已创建（免费版）", "user": safe}


def _admin_update_plan_impl(req: UpdateUserPlanRequest, actor: str) -> dict:
    if req.plan not in ["free", "professional", "business", "enterprise", "pro"]:
        raise HTTPException(400, detail="Invalid plan（不可将用户设为 owner）")
    store = "professional" if req.plan == "pro" else req.plan
    users = load_jsonl(USERS_FILE)
    found = False
    old_plan = None
    for u in users:
        if u.get("email") == req.email:
            old_plan = u.get("plan", "free")
            u["plan"] = store
            u["plan_updated_at"] = datetime.utcnow().isoformat()
            u["plan_updated_by"] = actor
            found = True
            break
    if not found:
        raise HTTPException(404, detail="User not found")
    rewrite_jsonl(USERS_FILE, users)
    append_admin_audit(
        "update_plan",
        actor,
        {"email": req.email, "old_plan": old_plan, "new_plan": store, "reason": req.reason},
    )
    return {"message": f"Plan updated to {store}", "email": req.email}


@router.post("/users/set-plan")
def admin_users_set_plan_alias(req: SetPlanAliasRequest, actor: str = Depends(verify_admin_access)):
    inner = UpdateUserPlanRequest(email=req.user_email, plan=req.new_plan, reason=req.reason)
    res = _admin_update_plan_impl(inner, actor)
    users = load_jsonl(USERS_FILE)
    for u in users:
        if u.get("email") == req.user_email:
            if req.expires_days > 0:
                u["expires_at"] = (datetime.utcnow() + timedelta(days=req.expires_days)).isoformat()
            else:
                u["expires_at"] = ""
            break
    rewrite_jsonl(USERS_FILE, users)
    return res


@router.post("/users/set-discount")
def admin_users_set_discount(req: SetDiscountRequest, actor: str = Depends(verify_admin_access)):
    users = load_jsonl(USERS_FILE)
    found = False
    for u in users:
        if u.get("email") == req.user_email:
            u["discount_percent"] = float(req.discount_percent)
            u["discount_reason"] = req.reason
            u["discount_updated_at"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(404, detail="User not found")
    rewrite_jsonl(USERS_FILE, users)
    append_admin_audit(
        "set_discount",
        actor,
        {"user_email": req.user_email, "discount_percent": req.discount_percent, "reason": req.reason},
    )
    return {"success": True, "message": "折扣已更新"}


@router.post("/user/update-plan")
def admin_update_plan(req: UpdateUserPlanRequest, actor: str = Depends(verify_admin_access)):
    return _admin_update_plan_impl(req, actor)


def _suspend_impl(email: str, suspended: bool, reason: str | None, actor: str) -> dict:
    users = load_jsonl(USERS_FILE)
    found = False
    for u in users:
        if u.get("email") == email:
            u["suspended"] = suspended
            u["active"] = not suspended
            u["suspension_reason"] = reason
            u["suspended_at"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(404, detail="User not found")
    rewrite_jsonl(USERS_FILE, users)
    append_admin_audit(
        "suspend_user",
        actor,
        {"email": email, "suspended": suspended, "reason": reason},
    )
    action = "suspended" if suspended else "unsuspended"
    return {"message": f"User {action} successfully"}


@router.post("/user/suspend")
def admin_suspend_user(req: SuspendUserRequest, actor: str = Depends(verify_admin_access)):
    return _suspend_impl(req.email, req.suspended, req.reason, actor)


@router.post("/users/suspend")
def admin_suspend_user_owner(req: OwnerSuspendRequest, actor: str = Depends(verify_admin_access)):
    return _suspend_impl(req.user_email, True, req.reason, actor)


@router.post("/users/unsuspend")
def admin_unsuspend_user_owner(req: OwnerSuspendRequest, actor: str = Depends(verify_admin_access)):
    return _suspend_impl(req.user_email, False, req.reason, actor)


@router.delete("/users/{user_email}")
def admin_delete_user(user_email: str, actor: str = Depends(verify_admin_access)):
    actor_em = actor if actor != "api_key" else ""
    if actor_em and user_email.lower() == actor_em.lower():
        raise HTTPException(400, detail="不能删除当前管理员账户")
    users = _load_all_users_list()
    n = len(users)
    users = [u for u in users if u.get("email", "").lower() != user_email.lower()]
    if len(users) == n:
        raise HTTPException(404, detail="用户不存在")
    _save_users(users)
    _audit_owner_file(actor, "delete_user", user_email, "永久删除")
    append_admin_audit("delete_user", actor, {"email": user_email})
    return {"success": True, "message": f"用户 {user_email} 已永久删除"}


@router.get("/tickets")
def admin_all_tickets(_actor: str = Depends(verify_admin_access), status: str | None = None):
    tickets = load_jsonl(TICKETS_FILE)
    if status:
        tickets = [t for t in tickets if t.get("status") == status]
    tickets.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"tickets": tickets, "total": len(tickets)}


@router.get("/revenue")
def admin_revenue(_actor: str = Depends(verify_admin_access)):
    users = load_jsonl(USERS_FILE)
    plan_counts = defaultdict(int)
    for u in users:
        plan_counts[u.get("plan", "free")] += 1
    mrr = sum(PLAN_PRICES.get(plan, 0) * count for plan, count in plan_counts.items())
    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "plan_breakdown": {
            plan: {"count": count, "revenue": PLAN_PRICES.get(plan, 0) * count}
            for plan, count in plan_counts.items()
        },
        "paying_users": sum(
            count for plan, count in plan_counts.items() if PLAN_PRICES.get(plan, 0) > 0
        ),
        "free_users": plan_counts.get("free", 0),
        "conversion_rate": round(
            sum(count for plan, count in plan_counts.items() if PLAN_PRICES.get(plan, 0) > 0)
            / max(len(users), 1)
            * 100,
            1,
        ),
    }
