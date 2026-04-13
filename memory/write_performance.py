content = """
import json
from datetime import datetime, timedelta
from pathlib import Path
from agents.meta_agent.registry import list_agents, update_agent_status
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

PERFORMANCE_LOG = Path("logs/agent_performance.jsonl")
MIN_SUCCESS_RATE = 0.6
MAX_ERROR_RATE = 0.4


def record_task_result(agent_name, task_id, success, tokens_used, elapsed_seconds):
    record = {
        "agent_name": agent_name,
        "task_id": task_id,
        "success": success,
        "tokens_used": tokens_used,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": datetime.utcnow().isoformat(),
    }
    PERFORMANCE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PERFORMANCE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + chr(10))


def get_agent_performance(agent_name, hours=24):
    if not PERFORMANCE_LOG.exists():
        return {"success_rate": 1.0, "error_rate": 0.0, "total_tasks": 0,
                "avg_tokens": 0, "avg_latency": 0}
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    records = []
    try:
        with open(PERFORMANCE_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("agent_name") == agent_name and r.get("timestamp", "") >= cutoff:
                    records.append(r)
    except Exception:
        return {"success_rate": 1.0, "error_rate": 0.0, "total_tasks": 0,
                "avg_tokens": 0, "avg_latency": 0}

    if not records:
        return {"success_rate": 1.0, "error_rate": 0.0, "total_tasks": 0,
                "avg_tokens": 0, "avg_latency": 0}

    total = len(records)
    successes = sum(1 for r in records if r.get("success"))
    success_rate = successes / total
    avg_tokens = sum(r.get("tokens_used", 0) for r in records) / total
    avg_latency = sum(r.get("elapsed_seconds", 0) for r in records) / total

    return {
        "agent_name": agent_name,
        "total_tasks": total,
        "success_rate": round(success_rate, 3),
        "error_rate": round(1 - success_rate, 3),
        "avg_tokens": round(avg_tokens, 1),
        "avg_latency_seconds": round(avg_latency, 1),
    }


def evaluate_all_agents():
    agents = list_agents(status="active")
    results = []
    for agent in agents:
        name = agent.get("name", "")
        perf = get_agent_performance(name)
        action = "ok"
        if perf["total_tasks"] >= 5:
            if perf["error_rate"] > MAX_ERROR_RATE:
                action = "flag_for_review"
                update_agent_status(name, "requires_review")
                write_audit_entry(AuditEntry(
                    agent_id=name,
                    task_id="performance_loop",
                    action="AGENT_FLAGGED_POOR_PERFORMANCE",
                    details={"error_rate": perf["error_rate"],
                             "success_rate": perf["success_rate"]},
                    success=False,
                ))
        perf["recommended_action"] = action
        results.append(perf)
    return results


def get_performance_summary():
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "agents": evaluate_all_agents(),
    }
"""

with open("self_monitoring/agent_performance.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("agent_performance.py created")
