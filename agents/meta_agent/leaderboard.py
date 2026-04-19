from __future__ import annotations
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AGENTS_FILE  = os.path.join(_BASE, "memory", "agents.jsonl")
TASKS_FILE   = os.path.join(_BASE, "memory", "tasks.jsonl")
AUDIT_FILE   = os.path.join(_BASE, "memory", "audit_log.jsonl")
MONITOR_FILE = os.path.join(_BASE, "memory", "agent_monitor.jsonl")


# ── helpers ────────────────────────────────────────────────────────────────

def _read(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def _user_agents(user_email: str) -> list[dict]:
    return [
        a for a in _read(AGENTS_FILE)
        if a.get("user_email", "").lower() == user_email.lower()
        and a.get("status", "active") != "deleted"
    ]


def _user_tasks(user_email: str) -> list[dict]:
    return [
        t for t in _read(TASKS_FILE)
        if t.get("user_email", "").lower() == user_email.lower()
    ]


def _agent_stats(agent: dict, tasks: list[dict]) -> dict:
    name = agent.get("name") or agent.get("role_name", "")
    agent_tasks = [t for t in tasks if t.get("agent_name") == name]
    total = len(agent_tasks)
    completed = sum(1 for t in agent_tasks if t.get("status") == "completed")
    failed = sum(1 for t in agent_tasks if t.get("status") == "failed")
    success_rate = round(completed / total * 100, 1) if total else 0.0
    total_tokens = sum(t.get("tokens_used", 0) for t in agent_tasks)
    avg_tokens = round(total_tokens / total, 0) if total else 0

    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    tasks_7d = sum(1 for t in agent_tasks if t.get("created_at", "") >= cutoff)

    timestamps = [t.get("created_at", "") for t in agent_tasks if t.get("created_at")]
    last_active = max(timestamps) if timestamps else ""

    dna_score = float(agent.get("dna_score", 0) or 0)
    rank_score = round(
        (success_rate * 0.4) + (dna_score * 0.3) + (min(tasks_7d * 10, 100) * 0.3), 2
    )

    return {
        "name": name,
        "department": agent.get("department", "general"),
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "success_rate": success_rate,
        "total_tokens": total_tokens,
        "avg_tokens_per_task": avg_tokens,
        "dna_score": dna_score,
        "grade": agent.get("grade", "F"),
        "tasks_last_7d": tasks_7d,
        "last_active": last_active,
        "rank_score": rank_score,
    }


# ── endpoints ──────────────────────────────────────────────────────────────

@router.get("/agents/{user_email}")
def get_agent_leaderboard(user_email: str) -> dict:
    """Full ranked leaderboard for all user agents."""
    agents = _user_agents(user_email)
    tasks = _user_tasks(user_email)
    rows = sorted(
        [_agent_stats(a, tasks) for a in agents],
        key=lambda x: x["rank_score"],
        reverse=True,
    )
    for i, row in enumerate(rows):
        row["rank"] = i + 1
    return {
        "agents": rows,
        "total": len(rows),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/top/{user_email}")
def get_top_agents(user_email: str) -> dict:
    """Return top 3 agents with gold/silver/bronze medals."""
    agents = _user_agents(user_email)
    tasks = _user_tasks(user_email)
    rows = sorted(
        [_agent_stats(a, tasks) for a in agents],
        key=lambda x: x["rank_score"],
        reverse=True,
    )
    def _pick(i: int) -> dict | None:
        return {**rows[i], "rank": i + 1} if len(rows) > i else None

    return {
        "gold":   _pick(0),
        "silver": _pick(1),
        "bronze": _pick(2),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/stats/{user_email}")
def get_platform_stats(user_email: str) -> dict:
    """Overall platform statistics for a user."""
    agents = _user_agents(user_email)
    tasks = _user_tasks(user_email)
    all_stats = [_agent_stats(a, tasks) for a in agents]

    total_tasks = sum(s["total_tasks"] for s in all_stats)
    total_tokens = sum(s["total_tokens"] for s in all_stats)
    avg_success = round(
        sum(s["success_rate"] for s in all_stats) / len(all_stats), 1
    ) if all_stats else 0.0

    most_used = max(all_stats, key=lambda x: x["total_tasks"], default=None)
    highest_dna = max(all_stats, key=lambda x: x["dna_score"], default=None)

    dept_rates: dict[str, list[float]] = defaultdict(list)
    for s in all_stats:
        dept_rates[s["department"]].append(s["success_rate"])
    best_dept = max(
        dept_rates, key=lambda d: sum(dept_rates[d]) / len(dept_rates[d]), default=None
    ) if dept_rates else None

    cutoff_30 = (datetime.utcnow() - timedelta(days=30)).isoformat()
    day_counts: dict[str, int] = defaultdict(int)
    for t in tasks:
        ts = t.get("created_at", "")
        if ts >= cutoff_30:
            day_counts[ts[:10]] += 1
    most_active_day = max(day_counts, key=lambda d: day_counts[d], default=None)

    return {
        "stats": {
            "best_performing_department": best_dept,
            "most_used_agent": most_used["name"] if most_used else None,
            "highest_dna_agent": highest_dna["name"] if highest_dna else None,
            "total_tasks_all_time": total_tasks,
            "total_tokens_all_time": total_tokens,
            "avg_success_rate": avg_success,
            "most_active_day": most_active_day,
        }
    }


@router.get("/department/{user_email}")
def get_department_breakdown(user_email: str) -> dict:
    """Per-department performance breakdown."""
    agents = _user_agents(user_email)
    tasks = _user_tasks(user_email)
    all_stats = [_agent_stats(a, tasks) for a in agents]

    dept_map: dict[str, list[dict]] = defaultdict(list)
    for s in all_stats:
        dept_map[s["department"]].append(s)

    departments = []
    for dept, members in sorted(dept_map.items()):
        best = max(members, key=lambda x: x["rank_score"])
        departments.append({
            "department": dept,
            "agent_count": len(members),
            "avg_success_rate": round(
                sum(m["success_rate"] for m in members) / len(members), 1
            ),
            "total_tasks": sum(m["total_tasks"] for m in members),
            "best_agent": best["name"],
            "best_score": best["rank_score"],
        })

    return {"departments": departments}
