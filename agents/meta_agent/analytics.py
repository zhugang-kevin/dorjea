import os
import json
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from agents.meta_agent.plan_enforcement import require_feature
from collections import defaultdict

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(require_feature("analytics"))],
)

AUDIT_FILE = "memory/audit_log.jsonl"
AGENTS_FILE = "memory/agents.jsonl"
TASKS_FILE = "memory/tasks.jsonl"

# Simple TTL cache: (result, timestamp)
_overview_cache: dict[int, tuple[dict, float]] = {}
_CACHE_TTL = 60  # seconds


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.min.replace(tzinfo=timezone.utc)

@router.get("/overview")
def analytics_overview(days: int = Query(7, ge=1, le=90, description="统计窗口天数")):
    # Return cached result if fresh
    cached = _overview_cache.get(days)
    if cached and (time.time() - cached[1]) < _CACHE_TTL:
        return cached[0]

    agents = load_jsonl(AGENTS_FILE)
    audit = load_jsonl(AUDIT_FILE)
    tasks = load_jsonl(TASKS_FILE)

    now = datetime.now(timezone.utc)
    last_nd = now - timedelta(days=days)
    last_30d = now - timedelta(days=30)

    # Agent stats
    active_agents = [a for a in agents if a.get("status") == "active"]
    total_agents = len(agents)

    # Task stats
    recent_tasks_nd = [t for t in tasks if _parse_dt(t.get("created_at", "")) > last_nd]
    recent_tasks_30d = [t for t in tasks if _parse_dt(t.get("created_at", "")) > last_30d]
    successful_tasks = [t for t in tasks if t.get("status") == "completed"]
    failed_tasks = [t for t in tasks if t.get("status") == "failed"]
    success_rate = round(len(successful_tasks) / max(len(tasks), 1) * 100, 1)

    # Audit stats
    recent_audit = [a for a in audit if _parse_dt(a.get("logged_at", "")) > last_nd]

    # Tokens by day (sliding window)
    tokens_by_day: dict[str, int] = defaultdict(int)
    tasks_by_day: dict[str, int] = defaultdict(int)
    for t in tasks:
        dt = _parse_dt(t.get("created_at", ""))
        if dt > last_nd:
            day = dt.strftime("%Y-%m-%d")
            tokens_by_day[day] += int(t.get("tokens_used", 0))
            tasks_by_day[day] += 1

    day_keys = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    tokens_chart = [{"date": d, "tokens": tokens_by_day.get(d, 0)} for d in day_keys]
    tasks_chart = [{"date": d, "tasks": tasks_by_day.get(d, 0)} for d in day_keys]

    # Top agents by task count
    agent_task_count: dict[str, int] = defaultdict(int)
    agent_tokens: dict[str, int] = defaultdict(int)
    for t in tasks:
        agent_task_count[t.get("agent_id", "unknown")] += 1
        agent_tokens[t.get("agent_id", "unknown")] += int(t.get("tokens_used", 0))

    top_agents = sorted(
        [{"agent": k, "tasks": v, "tokens": agent_tokens[k]} for k, v in agent_task_count.items()],
        key=lambda x: x["tasks"], reverse=True,
    )[:5]

    # Department breakdown
    dept_count: dict[str, int] = defaultdict(int)
    for a in agents:
        dept_count[a.get("department", "general")] += 1
    departments = [{"department": k, "agents": v} for k, v in dept_count.items()]

    # Agent quality scores
    dna_scores = [a.get("dna_score", 0) for a in agents if "dna_score" in a]
    avg_dna = round(sum(dna_scores) / max(len(dna_scores), 1), 1)
    grade_a = len([s for s in dna_scores if s >= 90])
    grade_b = len([s for s in dna_scores if 75 <= s < 90])
    grade_c = len([s for s in dna_scores if s < 75])

    result = {
        "summary": {
            "total_agents": total_agents,
            "active_agents": len(active_agents),
            "total_tasks": len(tasks),
            "tasks_last_7d": len(recent_tasks_nd),
            "tasks_last_30d": len(recent_tasks_30d),
            "success_rate": success_rate,
            "total_tokens_used": sum(int(t.get("tokens_used", 0)) for t in tasks),
            "audit_events_7d": len(recent_audit),
            "avg_dna_score": avg_dna,
        },
        "quality": {"grade_a": grade_a, "grade_b": grade_b, "grade_c": grade_c, "avg_score": avg_dna},
        "charts": {"tokens_by_day": tokens_chart, "tasks_by_day": tasks_chart},
        "top_agents": top_agents,
        "departments": departments,
    }
    _overview_cache[days] = (result, time.time())
    return result

@router.get("/agent/{agent_name}")
def agent_analytics(agent_name: str):
    tasks = load_jsonl(TASKS_FILE)
    agent_tasks = [t for t in tasks if t.get("agent_id") == agent_name]
    successful = [t for t in agent_tasks if t.get("status") == "completed"]
    failed = [t for t in agent_tasks if t.get("status") == "failed"]
    tokens = sum(t.get("tokens_used", 0) for t in agent_tasks)
    avg_tokens = round(tokens / max(len(agent_tasks), 1), 0)
    return {
        "agent": agent_name,
        "total_tasks": len(agent_tasks),
        "successful": len(successful),
        "failed": len(failed),
        "success_rate": round(len(successful) / max(len(agent_tasks), 1) * 100, 1),
        "total_tokens": tokens,
        "avg_tokens_per_task": avg_tokens,
        "recent_tasks": agent_tasks[-10:][::-1],
    }