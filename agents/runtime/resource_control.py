import json
from datetime import datetime, timedelta
from pathlib import Path
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

RESOURCE_LOG = Path("logs/resource_control.jsonl")

LIMITS = {
    "max_tokens_per_task": 20000,
    "max_tokens_per_day": 100000,
    "max_tasks_per_agent_per_hour": 50,
    "max_concurrent_tasks": 10,
    "max_runtime_seconds": 120,
}


def check_resource_limits(agent_name, tokens_requested, task_count_today=0):
    violations = []
    if tokens_requested > LIMITS["max_tokens_per_task"]:
        violations.append(
            "tokens_requested " + str(tokens_requested) +
            " exceeds max_tokens_per_task " + str(LIMITS["max_tokens_per_task"])
        )
    if task_count_today >= LIMITS["max_tasks_per_agent_per_hour"]:
        violations.append(
            "task_count_today " + str(task_count_today) +
            " exceeds max_tasks_per_agent_per_hour " +
            str(LIMITS["max_tasks_per_agent_per_hour"])
        )
    if violations:
        write_audit_entry(AuditEntry(
            agent_id=agent_name,
            task_id="resource_control",
            action="RESOURCE_LIMIT_VIOLATED",
            details={"violations": violations},
            success=False,
        ))
    return len(violations) == 0, violations


def record_resource_usage(agent_name, task_id, tokens_used, runtime_seconds):
    record = {
        "agent_name": agent_name,
        "task_id": task_id,
        "tokens_used": tokens_used,
        "runtime_seconds": runtime_seconds,
        "timestamp": datetime.utcnow().isoformat(),
    }
    RESOURCE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RESOURCE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + chr(10))


def get_resource_summary(hours=24):
    if not RESOURCE_LOG.exists():
        return {"total_tokens": 0, "total_tasks": 0, "avg_runtime": 0}
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    records = []
    try:
        with open(RESOURCE_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if r.get("timestamp", "") >= cutoff:
                        records.append(r)
    except Exception:
        pass
    if not records:
        return {"total_tokens": 0, "total_tasks": 0, "avg_runtime": 0}
    total_tokens = sum(r.get("tokens_used", 0) for r in records)
    avg_runtime = sum(r.get("runtime_seconds", 0) for r in records) / len(records)
    return {
        "total_tokens": total_tokens,
        "total_tasks": len(records),
        "avg_runtime_seconds": round(avg_runtime, 1),
        "budget_used_pct": round(total_tokens / LIMITS["max_tokens_per_day"] * 100, 1),
    }