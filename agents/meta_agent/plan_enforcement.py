"""
套餐权限执行模块 — 元芯智能 AgentCore
权限层级: owner > enterprise > business > pro/professional > free
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Callable

from fastapi import Header, HTTPException

from agents.meta_agent.auth import (
    check_daily_tokens,
    decode_access_token,
    get_user_by_token,
)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "").strip().lower()
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "").strip()

USERS_FILE = "memory/users.jsonl"
AGENTS_FILE = "memory/agents.jsonl"
CLONES_FILE = "memory/department_clones.jsonl"

PLAN_RANK: dict[str, int] = {
    "free": 0,
    "pro": 1,
    "professional": 1,
    "business": 2,
    "enterprise": 3,
    "owner": 99,
}

DAILY_TOKEN_LIMITS: dict[str, int] = {
    "free": 5000,
    "pro": 50000,
    "professional": 50000,
    "business": 150000,
    "enterprise": 500000,
    "owner": 999999999,
}

MAX_AGENTS: dict[str, int] = {
    "free": 3,
    "pro": 20,
    "professional": 20,
    "business": 100,
    "enterprise": -1,
    "owner": -1,
}

MAX_CLONES: dict[str, int] = {
    "free": 0,
    "pro": 0,
    "professional": 0,
    "business": 3,
    "enterprise": 10,
    "owner": 1000,
}

PRICE_USD: dict[str, int] = {
    "free": 0,
    "pro": 29,
    "professional": 29,
    "business": 99,
    "enterprise": 0,
    "owner": 0,
}

FEATURE_MIN_PLAN: dict[str, str] = {
    "overview": "free",
    "agents": "free",
    "create": "free",
    "tasks": "free",
    "templates": "free",
    "billing": "free",
    "account": "free",
    "usage": "free",
    "security": "free",
    "provider_keys": "free",
    "user_keys": "free",
    "help": "free",
    "support": "free",
    "settings": "free",
    "audit": "pro",
    "audit_log": "professional",
    "analytics": "pro",
    "api_keys": "professional",
    "memory": "pro",
    "memory_knowledge": "professional",
    "integrations": "pro",
    "tools_integrations": "professional",
    "workflows": "pro",
    "referral": "pro",
    "monitor": "business",
    "leaderboard": "business",
    "clones": "business",
    "workflow_builder": "business",
    "admin": "owner",
    "admin_generate": "owner",
    "admin_users": "owner",
    "admin_stats": "owner",
}

FEATURE_NAMES_CN: dict[str, str] = {
    "audit": "操作日志",
    "audit_log": "操作日志",
    "analytics": "数据分析",
    "api_keys": "API密钥管理",
    "provider_keys": "AI 服务密钥",
    "user_keys": "AI 服务密钥",
    "memory": "记忆库管理",
    "memory_knowledge": "知识库文档",
    "integrations": "工具集成",
    "tools_integrations": "工具集成",
    "workflows": "工作流",
    "referral": "推荐计划",
    "monitor": "实时监控面板",
    "leaderboard": "AI助手排行榜",
    "clones": "部门克隆",
    "workflow_builder": "可视化工作流编辑器",
    "admin": "管理员控制台",
    "admin_generate": "账户生成功能",
    "admin_users": "用户管理",
    "admin_stats": "管理统计",
}

PLAN_NAMES_CN: dict[str, str] = {
    "free": "免费版",
    "pro": "专业版",
    "professional": "专业版",
    "business": "商业版",
    "enterprise": "企业版",
    "owner": "系统所有者",
}

PLAN_LABEL_ZH = PLAN_NAMES_CN


def _unlimited_agents(n: int) -> int:
    return 999999 if n < 0 else n


def _build_plan_limits_row(key: str) -> dict:
    daily = DAILY_TOKEN_LIMITS.get(key, 5000)
    ma = _unlimited_agents(MAX_AGENTS.get(key, 3))
    mc = MAX_CLONES.get(key, 0)
    return {
        "daily_tokens": daily,
        "max_agents": ma,
        "max_clones": mc,
        "price_usd": PRICE_USD.get(key, 0),
    }


PLAN_LIMITS: dict[str, dict] = {
    k: _build_plan_limits_row(k) for k in ("free", "pro", "professional", "business", "enterprise", "owner")
}


def normalize_plan_key(plan: str | None) -> str:
    if not plan:
        return "free"
    p = str(plan).lower().strip()
    if p == "pro":
        return "professional"
    return p


def load_user(email: str):
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                u = json.loads(line)
                if u.get("email", "").lower() == (email or "").lower().strip():
                    return u
    return None


def is_owner(email: str) -> bool:
    e = (email or "").strip().lower()
    if not e:
        return False
    if ADMIN_EMAIL and e == ADMIN_EMAIL:
        return True
    if OWNER_EMAIL and e == OWNER_EMAIL:
        return True
    u = load_user(e)
    return bool(u and u.get("is_owner"))


def is_owner_email(email: str) -> bool:
    return is_owner(email)


def get_user_plan(email: str) -> str:
    if not email:
        return "free"
    e = email.lower().strip()
    if is_owner(e):
        return "owner"
    user = load_user(e)
    if not user:
        return "free"
    return str(user.get("plan", "free"))


def get_plan_limits(plan: str) -> dict:
    p = normalize_plan_key(plan)
    return PLAN_LIMITS.get(p, PLAN_LIMITS["free"])


def plan_meets_minimum(user_plan: str, minimum_plan: str) -> bool:
    up = normalize_plan_key(user_plan)
    mp = normalize_plan_key(minimum_plan)
    if up == "owner":
        return True
    return PLAN_RANK.get(up, 0) >= PLAN_RANK.get(mp, 0)


def upgrade_hint_zh(minimum_plan: str) -> str:
    mp = normalize_plan_key(minimum_plan)
    label = PLAN_NAMES_CN.get(mp, minimum_plan)
    return "此功能需要「" + label + "」或以上套餐。请前往 /pricing 升级。"


def feature_access_map(email: str) -> dict[str, bool]:
    """传入邮箱，或传入套餐 slug（不含 @ 时按套餐名解析，兼容旧调用）。"""
    s = (email or "").strip()
    if "@" in s:
        plan = get_user_plan(s)
    else:
        plan = s if s else "free"
    up = normalize_plan_key(plan)
    if up == "owner":
        return {key: True for key in FEATURE_MIN_PLAN}
    return {key: plan_meets_minimum(up, min_p) for key, min_p in FEATURE_MIN_PLAN.items()}


def strip_bearer_token(raw: str) -> str:
    t = raw.strip()
    if t.startswith("Bearer "):
        t = t[7:].strip()
    if t.startswith("admin_"):
        t = t[6:]
    return t


def parse_bearer_email(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        return ""
    token = strip_bearer_token(authorization)
    user = get_user_by_token(token)
    if not user:
        return ""
    em = user.get("email")
    return str(em) if em else ""


def resolve_scoped_user_email(
    requested_email: str | None,
    authorization: str | None,
    *,
    allow_owner_override: bool = True,
) -> str:
    """Return the authenticated email unless an owner is explicitly overriding it."""
    current_email = parse_bearer_email(authorization)
    if not current_email:
        raise HTTPException(
            status_code=401,
            detail="请先登录后再使用此功能。请在请求头携带 Authorization: Bearer <令牌>。",
        )
    requested = (requested_email or "").strip().lower()
    if not requested or requested == current_email.lower():
        return current_email
    if allow_owner_override and is_owner(current_email):
        return requested
    raise HTTPException(status_code=403, detail="不能访问其他用户的数据。")


def resolve_super_admin_actor(authorization: str) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="无权访问管理接口")
    raw = authorization.replace("Bearer ", "", 1).strip()
    token = strip_bearer_token(raw)
    if ADMIN_SECRET_KEY and hmac.compare_digest(token, ADMIN_SECRET_KEY):
        return "api_key"
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=403, detail="无权访问管理接口（令牌无效或已过期）")
    if payload.get("is_owner"):
        sub = payload.get("sub") or "owner_unknown"
        return str(sub)
    raise HTTPException(
        status_code=403,
        detail="需要超级管理员（OWNER）令牌或正确的 ADMIN_SECRET_KEY",
    )


def require_super_admin(authorization: str = Header(...)) -> str:
    return resolve_super_admin_actor(authorization)


def require_owner(authorization: str | None = None) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return resolve_super_admin_actor(authorization)


def require_auth_email(authorization: str | None = Header(None)) -> str:
    email = parse_bearer_email(authorization)
    if not email:
        raise HTTPException(
            status_code=401,
            detail="请先登录后再使用此功能。请在请求头携带 Authorization: Bearer <令牌>。",
        )
    return email


def enforce_plan_feature(user_email: str, feature: str) -> None:
    if is_owner(user_email):
        return
    minimum = FEATURE_MIN_PLAN.get(feature)
    if minimum is None:
        return
    plan = get_user_plan(user_email)
    if not plan_meets_minimum(plan, minimum):
        mp = normalize_plan_key(minimum)
        fname = FEATURE_NAMES_CN.get(feature, feature)
        req_name = PLAN_NAMES_CN.get(mp, mp)
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PLAN_REQUIRED",
                "message": "「" + fname + "」需要" + req_name + "或以上套餐",
                "feature": feature,
                "required_plan": minimum,
                "current_plan": plan,
                "upgrade_url": "/pricing",
            },
        )


def require_feature(feature: str, authorization: str | None = None) -> Callable | str:
    if authorization is not None:
        email = parse_bearer_email(authorization)
        if not email:
            raise HTTPException(
                status_code=401,
                detail="请先登录后再使用此功能。请在请求头携带 Authorization: Bearer <令牌>。",
            )
        enforce_plan_feature(email, feature)
        return email

    def _checker(authorization: str | None = Header(None)) -> None:
        em = parse_bearer_email(authorization)
        if not em:
            raise HTTPException(
                status_code=401,
                detail="请先登录后再使用此功能。请在请求头携带 Authorization: Bearer <令牌>。",
            )
        enforce_plan_feature(em, feature)

    return _checker


def enforce_daily_tokens(email: str, tokens: int) -> None:
    if is_owner(email):
        return
    user = load_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或未登录。")
    ok, used, limit = check_daily_tokens(user, tokens)
    if ok:
        return
    remaining = max(0, limit - used)
    plan = get_user_plan(email)
    hint = upgrade_hint_zh("professional") if plan == "free" else "请联系管理员或升级更高套餐。"
    raise HTTPException(
        status_code=429,
        detail={
            "code": "TOKEN_LIMIT_EXCEEDED",
            "message": "今日 Token 额度不足，请升级套餐或明日再试。",
            "remaining": int(remaining),
            "limit": int(limit),
            "used": int(used),
            "hint": hint,
        },
    )


enforce_daily_tokens_allowance = enforce_daily_tokens


def count_user_agents(email: str) -> int:
    if not os.path.exists(AGENTS_FILE):
        return 0
    with open(AGENTS_FILE, encoding="utf-8") as f:
        agents = [json.loads(l) for l in f if l.strip()]
    return len(
        [
            a
            for a in agents
            if a.get("user_email") == email and a.get("status") != "retired" and not a.get("deleted")
        ]
    )


def count_user_clones(email: str) -> int:
    if not os.path.exists(CLONES_FILE):
        return 0
    with open(CLONES_FILE, encoding="utf-8") as f:
        clones = [json.loads(l) for l in f if l.strip()]
    return len([c for c in clones if c.get("user_email") == email and not c.get("deleted")])


def enforce_agent_limit(email: str, current_count: int | None = None) -> None:
    if current_count is None:
        current_count = count_user_agents(email)
    plan = normalize_plan_key(get_user_plan(email))
    limits = get_plan_limits(plan)
    max_allowed = limits["max_agents"]
    if max_allowed >= 999000:
        return
    if current_count >= max_allowed:
        label = PLAN_NAMES_CN.get(plan, plan)
        msg = (
            "当前套餐「"
            + label
            + "」最多创建 "
            + str(max_allowed)
            + " 个 AI 助手，您已有 "
            + str(current_count)
            + " 个。请前往 /pricing 升级。"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": msg, "current_plan": plan},
        )


def enforce_clone_limit(email: str, current_count: int | None = None) -> None:
    if current_count is None:
        current_count = count_user_clones(email)
    plan = normalize_plan_key(get_user_plan(email))
    limits = get_plan_limits(plan)
    max_allowed = limits["max_clones"]
    if max_allowed == 0:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "部门克隆为「商业版」及以上功能。请升级后使用。",
                "required_plan": "business",
                "current_plan": plan,
            },
        )
    if max_allowed >= 999000:
        return
    if current_count >= max_allowed:
        msg = "克隆数量已达上限（" + str(max_allowed) + "）。请前往 /pricing 升级。"
        raise HTTPException(
            status_code=403,
            detail={"message": msg, "current_plan": plan},
        )


def check_feature_access(email: str, feature: str) -> None:
    enforce_plan_feature(email, feature)


def enforce_token_budget(email: str, tokens_requested: int) -> None:
    enforce_daily_tokens(email, tokens_requested)


def get_plan_info(email: str) -> dict:
    plan = normalize_plan_key(get_user_plan(email))
    limits = get_plan_limits(plan)
    ma = limits["max_agents"]
    mc = limits["max_clones"]
    ca = count_user_agents(email)
    cc = count_user_clones(email)
    rem_a = None if ma >= 999000 else ma - ca
    rem_c = None if mc >= 999000 else mc - cc
    return {
        "plan": plan,
        "limits": limits,
        "usage": {"agents": ca, "clones": cc},
        "remaining": {"agents": rem_a, "clones": rem_c},
        "feature_access": feature_access_map(email),
    }
