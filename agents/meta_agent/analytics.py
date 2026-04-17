import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter
from collections import defaultdict

router = APIRouter(prefix="/analytics", tags=["Analytics"])

AUDIT_FILE = "memory/audit_log.jsonl"
AGENTS_FILE = "memory/agents.jsonl"
TASKS_FILE = "memory/tasks.jsonl"

def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

@router.get("/overview")
def analytics_overview():
    agents = load_jsonl(AGENTS_FILE)
    audit = load_jsonl(AUDIT_FILE)
    tasks = load_jsonl(TASKS_FILE)

    now = datetime.utcnow()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    def parse_dt(s):
        try:
            return datetime.fromisoformat(s.replace("Z",""))
        except:
            return datetime.min

    # Agent stats
    active_agents = [a for a in agents if a.get("status") == "active"]
    total_agents = len(agents)

    # Task stats
    recent_tasks_7d = [t for t in tasks if parse_dt(t.get("created_at","")) > last_7d]
    recent_tasks_30d = [t for t in tasks if parse_dt(t.get("created_at","")) > last_30d]
    successful_tasks = [t for t in tasks if t.get("status") == "completed"]
    failed_tasks = [t for t in tasks if t.get("status") == "failed"]
    success_rate = round(len(successful_tasks) / max(len(tasks), 1) * 100, 1)

    # Audit stats
    recent_audit = [a for a in audit if parse_dt(a.get("logged_at","")) > last_7d]

    # Tokens by day (last 7 days)
    tokens_by_day = defaultdict(int)
    tasks_by_day = defaultdict(int)
    for t in tasks:
        dt = parse_dt(t.get("created_at",""))
        if dt > last_7d:
            day = dt.strftime("%Y-%m-%d")
            tokens_by_day[day] += t.get("tokens_used", 0)
            tasks_by_day[day] += 1

    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6,-1,-1)]
    tokens_chart = [{"date": d, "tokens": tokens_by_day.get(d, 0)} for d in days]
    tasks_chart = [{"date": d, "tasks": tasks_by_day.get(d, 0)} for d in days]

    # Top agents by task count
    agent_task_count = defaultdict(int)
    agent_tokens = defaultdict(int)
    for t in tasks:
        agent_task_count[t.get("agent_id","unknown")] += 1
        agent_tokens[t.get("agent_id","unknown")] += t.get("tokens_used", 0)

    top_agents = sorted(
        [{"agent": k, "tasks": v, "tokens": agent_tokens[k]}
         for k, v in agent_task_count.items()],
        key=lambda x: x["tasks"], reverse=True
    )[:5]

    # Department breakdown
    dept_count = defaultdict(int)
    for a in agents:
        dept_count[a.get("department", "general")] += 1
    departments = [{"department": k, "agents": v} for k, v in dept_count.items()]

    # Agent quality scores
    dna_scores = [a.get("dna_score", 0) for a in agents if "dna_score" in a]
    avg_dna = round(sum(dna_scores) / max(len(dna_scores), 1), 1)
    grade_a = len([s for s in dna_scores if s >= 90])
    grade_b = len([s for s in dna_scores if 75 <= s < 90])
    grade_c = len([s for s in dna_scores if s < 75])

    return {
        "summary": {
            "total_agents": total_agents,
            "active_agents": len(active_agents),
            "total_tasks": len(tasks),
            "tasks_last_7d": len(recent_tasks_7d),
            "tasks_last_30d": len(recent_tasks_30d),
            "success_rate": success_rate,
            "total_tokens_used": sum(t.get("tokens_used",0) for t in tasks),
            "audit_events_7d": len(recent_audit),
            "avg_dna_score": avg_dna,
        },
        "quality": {
            "grade_a": grade_a,
            "grade_b": grade_b,
            "grade_c": grade_c,
            "avg_score": avg_dna,
        },
        "charts": {
            "tokens_by_day": tokens_chart,
            "tasks_by_day": tasks_chart,
        },
        "top_agents": top_agents,
        "departments": departments,
    }

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