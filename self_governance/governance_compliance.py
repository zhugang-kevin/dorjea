from datetime import datetime
from agents.meta_agent.audit_logger import write_audit_entry, read_all_entries
from agents.meta_agent.models import AuditEntry

GOVERNANCE_RULES = [
    "agents cannot modify core",
    "agents cannot delete logs",
    "agents cannot create agents",
    "agents cannot modify config",
    "agents cannot escalate own permissions",
]


def check_governance_compliance(agent_name, action):
    violations = []
    action_lower = action.lower()
    for rule in GOVERNANCE_RULES:
        keywords = rule.replace("agents cannot ", "").split()
        if all(kw in action_lower for kw in keywords):
            violations.append("Governance violation: " + rule)
    if violations:
        write_audit_entry(AuditEntry(
            agent_id=agent_name,
            task_id="governance_loop",
            action="GOVERNANCE_VIOLATION_DETECTED",
            details={"action": action[:200], "violations": violations},
            success=False,
        ))
    return len(violations) == 0, violations


def run_governance_audit():
    entries = read_all_entries(limit=100)
    violations_found = []
    for entry in entries:
        action = entry.action.lower()
        for rule in GOVERNANCE_RULES:
            keywords = rule.replace("agents cannot ", "").split()
            if all(kw in action for kw in keywords) and not entry.success:
                violations_found.append({
                    "agent_id": entry.agent_id,
                    "action": entry.action,
                    "rule_violated": rule,
                    "logged_at": entry.logged_at,
                })
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "violations_found": len(violations_found),
        "violations": violations_found[:10],
        "status": "VIOLATIONS_DETECTED" if violations_found else "COMPLIANT",
    }
