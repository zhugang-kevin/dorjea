"""订阅与账单路由（套餐定义：中文名称，人民币标价，与 auth.PLAN_LIMITS 对齐）。"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from agents.meta_agent.plan_enforcement import parse_bearer_email, resolve_scoped_user_email
from pydantic import BaseModel

router = APIRouter(prefix="/billing", tags=["Billing"])
USERS_FILE = "memory/users.jsonl"
BILLING_FILE = "memory/billing_history.jsonl"

# 人民币月费（标价，实际支付以支付模块为准）
PLAN_PRICES_CNY = {
    "free": 0,
    "professional": 199,
    "business": 599,
    "enterprise": 0,
}

# 兼容旧字段名（美元占位，不再作为对外主价）
PLAN_PRICES = {
    "free": 0,
    "professional": PLAN_PRICES_CNY["professional"],
    "business": PLAN_PRICES_CNY["business"],
    "enterprise": 0,
}

# 四档套餐（中文 + 每日 tokens 与 auth 一致）
PLAN_DETAILS = {
    "free": {
        "name_zh": "免费版",
        "name": "免费版",
        "daily_tokens": 5000,
        "max_agents": 3,
        "max_clones": 0,
        "price_cny_per_month": 0,
        "summary_zh": "试用与轻量体验，含基础 AI 助手数量与每日令牌额度。",
    },
    "professional": {
        "name_zh": "专业版",
        "name": "专业版",
        "daily_tokens": 50000,
        "max_agents": 20,
        "max_clones": 0,
        "price_cny_per_month": PLAN_PRICES_CNY["professional"],
        "summary_zh": "适合成长型团队，更高每日令牌与克隆额度。",
    },
    "business": {
        "name_zh": "商业版",
        "name": "商业版",
        "daily_tokens": 150000,
        "max_agents": 100,
        "max_clones": 3,
        "price_cny_per_month": PLAN_PRICES_CNY["business"],
        "summary_zh": "适合多部门协作与中高并发任务场景。",
    },
    "enterprise": {
        "name_zh": "企业版",
        "name": "企业版",
        "daily_tokens": 500000,
        "max_agents": 500,
        "max_clones": 10,
        "price_cny_per_month": 0,
        "summary_zh": "专有云、定制化与对公合同，请联系商务获取报价。",
    },
}


def load_user(email: str):
    """按邮箱加载用户记录。"""
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                u = json.loads(line)
                if u.get("email") == email:
                    return u
    return None


def load_billing(email: str):
    """加载用户账单流水。"""
    if not os.path.exists(BILLING_FILE):
        return []
    with open(BILLING_FILE, encoding="utf-8") as f:
        all_records = [json.loads(line) for line in f if line.strip()]
    return [r for r in all_records if r.get("user_email") == email]


def save_billing(record: dict) -> None:
    """追加一条账单记录。"""
    Path("memory").mkdir(parents=True, exist_ok=True)
    with open(BILLING_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class RefundRequest(BaseModel):
    """退款申请。"""

    user_email: str
    reason: str
    additional_info: Optional[str] = ""


class CancelRequest(BaseModel):
    """取消订阅申请。"""

    user_email: str
    reason: str


@router.get("/info")
def get_billing_info(authorization: str | None = Header(None)) -> dict:
    """当前登录用户账单摘要（GET /billing/info）。"""
    email = parse_bearer_email(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="请先登录")
    return get_billing_summary(email)


@router.get("/history")
def get_billing_history_me(
    authorization: str | None = Header(None),
    page: int = 1,
) -> dict:
    """当前用户账单历史，分页（GET /billing/history）。"""
    email = parse_bearer_email(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="请先登录")
    history = load_billing(email)
    history_rev = history[::-1]
    page_size = 20
    total = len(history_rev)
    start = max(0, (page - 1) * page_size)
    chunk = history_rev[start : start + page_size]
    return {"records": chunk, "total": total, "page": page, "page_size": page_size}


@router.get("/summary/{user_email}")
def get_billing_summary(user_email: str, authorization: str | None = Header(None)):
    """返回当前套餐、人民币价格与近期流水。"""
    user_email = resolve_scoped_user_email(user_email, authorization)
    user = load_user(user_email)
    if not user:
        raise HTTPException(404, detail="User not found")
    plan = user.get("plan", "free")
    price = PLAN_PRICES_CNY.get(plan, 0)
    plan_info = PLAN_DETAILS.get(plan, PLAN_DETAILS["free"])
    created_at = user.get("created_at", datetime.utcnow().isoformat())
    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z", ""))
    except Exception:
        created_dt = datetime.utcnow()
    now = datetime.utcnow()
    if plan != "free" and price > 0:
        billing_day = created_dt.day
        if now.day >= billing_day:
            next_billing = now.replace(day=billing_day) + timedelta(days=32)
            next_billing = next_billing.replace(day=billing_day)
        else:
            next_billing = now.replace(day=billing_day)
        days_in_period = 30
        days_used = (
            (now - now.replace(day=billing_day)).days
            if now.day >= billing_day
            else 30 - (now.replace(day=billing_day) - now).days
        )
        days_remaining = days_in_period - days_used
        amount_used = round(price * days_used / days_in_period, 2)
        refund_amount = round(price - amount_used, 2)
    else:
        next_billing = None
        days_remaining = 0
        amount_used = 0
        refund_amount = 0
        if plan == "free":
            trial_days = user.get("trial_days", 3)
            trial_end = created_dt + timedelta(days=trial_days)
            days_remaining = max(0, (trial_end - now).days)
    history = load_billing(user_email)
    return {
        "plan": plan,
        "plan_name": plan_info["name_zh"],
        "price_per_month_cny": price,
        "currency": "CNY",
        "next_billing_date": next_billing.isoformat() if next_billing else None,
        "days_remaining": days_remaining,
        "amount_used_this_period": amount_used,
        "refund_eligible": refund_amount,
        "plan_details": plan_info,
        "member_since": created_at,
        "billing_history": history[-10:][::-1],
        "payment_method": user.get("payment_method"),
    }


@router.post("/refund-request")
def request_refund(req: RefundRequest, authorization: str | None = Header(None)):
    """提交退款申请（人工审核）。"""
    user_email = resolve_scoped_user_email(req.user_email, authorization)
    user = load_user(user_email)
    if not user:
        raise HTTPException(404, detail="User not found")
    plan = user.get("plan", "free")
    price = PLAN_PRICES_CNY.get(plan, 0)
    if price == 0:
        raise HTTPException(400, detail="No active paid subscription to refund")
    now = datetime.utcnow()
    created_at = user.get("created_at", now.isoformat())
    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z", ""))
    except Exception:
        created_dt = now
    billing_day = created_dt.day
    if now.day >= billing_day:
        period_start = now.replace(day=billing_day)
    else:
        prev_month = now.replace(day=1) - timedelta(days=1)
        period_start = prev_month.replace(day=billing_day)
    days_used = (now - period_start).days
    days_in_period = 30
    amount_used = round(price * days_used / days_in_period, 2)
    refund_amount = round(price - amount_used, 2)
    record = {
        "type": "refund_request",
        "user_email": user_email,
        "plan": plan,
        "price_paid_cny": price,
        "days_used": days_used,
        "amount_used": amount_used,
        "refund_amount_cny": refund_amount,
        "reason": req.reason,
        "additional_info": req.additional_info,
        "status": "pending",
        "requested_at": now.isoformat(),
    }
    save_billing(record)
    return {
        "message": "退款申请已提交",
        "refund_amount_cny": refund_amount,
        "days_used": days_used,
        "processing_time": "3-5 个工作日",
        "contact": "billing@yuancore.cn",
    }


@router.post("/cancel")
def cancel_subscription(req: CancelRequest, authorization: str | None = Header(None)):
    """取消订阅请求。"""
    user_email = resolve_scoped_user_email(req.user_email, authorization)
    user = load_user(user_email)
    if not user:
        raise HTTPException(404, detail="User not found")
    plan = user.get("plan", "free")
    if plan == "free":
        raise HTTPException(400, detail="No paid subscription to cancel")
    record = {
        "type": "cancellation_request",
        "user_email": user_email,
        "plan": plan,
        "reason": req.reason,
        "status": "pending",
        "requested_at": datetime.utcnow().isoformat(),
    }
    save_billing(record)
    return {
        "message": "已收到取消申请",
        "effective_date": "当前计费周期结束时",
        "note": "周期内权益仍有效，到期后不再扣费。",
        "contact": "billing@yuancore.cn",
    }


@router.get("/history/{user_email}")
def get_billing_history(user_email: str, authorization: str | None = Header(None)):
    """账单历史列表。"""
    user_email = resolve_scoped_user_email(user_email, authorization)
    history = load_billing(user_email)
    return {"history": history[::-1], "total": len(history)}


@router.get("/plans/catalog")
def get_plans_catalog():
    """对外套餐清单（中文 + 人民币 + 令牌额度）。"""
    return {
        "currency": "CNY",
        "plans": PLAN_DETAILS,
        "prices_cny": PLAN_PRICES_CNY,
    }
