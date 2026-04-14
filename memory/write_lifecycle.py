content = """
import json
from datetime import datetime
from pathlib import Path
from agents.meta_agent.registry import get_agent, update_agent_status, list_agents
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

LIFECYCLE_STAGES = [
    "generated",
    "validated",
    "deployed",
    "monitored",
    "updated",
    "retired",
]

VALID_TRANSITIONS = {
    "generated":  ["validated", "retired"],
    "validated":  ["deployed", "retired"],
    "deployed":   ["monitored", "updated", "retired"],
    "monitored":  ["updated", "retired"],
    "updated":    ["monitored", "retired"],
    "active":     ["monitored", "updated", "retired"],
    "idle":       ["monitored", "updated", "retired"],
    "frozen":     ["retired", "deployed"],
    "requires_review": ["validated", "retired"],
    "archived":   ["retired"],
}

LIFECYCLE_LOG = Path("logs/lifecycle.jsonl")


def log_transition(agent_name, from_stage, to_stage, reason=""):
    record = {
        "agent_name": agent_name,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }
    LIFECYCLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LIFECYCLE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + chr(10))
    write_audit_entry(AuditEntry(
        agent_id=agent_name,
        task_id="lifecycle",
        action="LIFECYCLE_TRANSITION",
        details={"from": from_stage, "to": to_stage, "reason": reason},
        success=True,
    ))


def transition_agent(agent_name, to_stage, reason=""):
    agent = get_agent(agent_name)
    if not agent:
        return False, "Agent not found: " + agent_name
    current = agent.get("status", "generated")
    allowed = VALID_TRANSITIONS.get(current, [])
    if to_stage not in allowed:
        return False, "Invalid transition: " + current + " -> " + to_stage + ". Allowed: " + str(allowed)
    update_agent_status(agent_name, to_stage)
    log_transition(agent_name, current, to_stage, reason)
    return True, "Transitioned " + agent_name + " from " + current + " to " + to_stage


def deploy_agent(agent_name):
    return transition_agent(agent_name, "deployed", "Manual deployment by founder")


def retire_agent(agent_name, reason="Retired by founder"):
    return transition_agent(agent_name, "retired", reason)


def update_agent(agent_name, reason="Version update"):
    return transition_agent(agent_name, "updated", reason)


def get_lifecycle_history(agent_name):
    if not LIFECYCLE_LOG.exists():
        return []
    records = []
    try:
        with open(LIFECYCLE_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if r.get("agent_name") == agent_name:
                        records.append(r)
    except Exception:
        pass
    return records


def get_lifecycle_summary():
    agents = list_agents()
    summary = {}
    for agent in agents:
        status = agent.get("status", "unknown")
        summary[status] = summary.get(status, 0) + 1
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_agents": len(agents),
        "by_stage": summary,
    }
"""

with open("agents/meta_agent/lifecycle_manager.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("lifecycle_manager.py created")
