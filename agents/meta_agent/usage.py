"""用量统计路由 — 元芯智能 AgentCore"""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, HTTPException

from agents.meta_agent.plan_enforcement import DAILY_TOKEN_LIMITS, get_user_plan, load_user, parse_bearer_email

router = APIRouter(prefix="/usage", tags=["用量统计"])

TASKS_FILE = "memory/tasks.jsonl"


def _load_tasks() -> list[dict]:
    if not os.path.exists(TASKS_FILE):
        return []
    rows = []
    with open(TASKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


@router.get("/stats")
def get_usage_stats(authorization: str | None = Header(None)) -> dict:
    """当前登录用户的 Token / 请求用量摘要，含 7 天趋势。"""
    email = parse_bearer_email(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="请先登录")
    plan = get_user_plan(email)
    user = load_user(email)
    daily_limit = int(DAILY_TOKEN_LIMITS.get(plan, 5000))
    used_today = int(user.get("daily_tokens_used", 0)) if user else 0

    # Build 7-day trend from tasks file
    now = datetime.now(timezone.utc)
    trend: list[dict] = []
    for offset in range(6, -1, -1):
        day = now - timedelta(days=offset)
        day_str = day.strftime("%Y-%m-%d")
        trend.append({"date": day_str, "tokens": 0, "requests": 0})

    tasks = _load_tasks()
    for task in tasks:
        if task.get("user_email", "").lower() != email.lower():
            continue
        raw_ts = task.get("created_at", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if (now - ts).days > 6:
            continue
        day_str = ts.strftime("%Y-%m-%d")
        for entry in trend:
            if entry["date"] == day_str:
                entry["tokens"] += int(task.get("tokens_used", 0))
                entry["requests"] += 1
                break

    monthly_tokens = sum(e["tokens"] for e in trend)
    cost_per_1k = 0.02  # CNY estimate
    cost_cny = round(monthly_tokens / 1000 * cost_per_1k, 4)

    return {
        "today": {
            "tokens_used": used_today,
            "tokens_limit": daily_limit,
            "requests": trend[-1]["requests"] if trend else 0,
        },
        "month": {
            "tokens_used": monthly_tokens,
            "cost_cny": cost_cny,
            "requests": sum(e["requests"] for e in trend),
        },
        "trend": trend,
    }
