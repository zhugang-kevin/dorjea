content = """
from agents.runtime.ai_clients import ClaudeClient
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from datetime import datetime

claude = ClaudeClient()

PLANNING_SYSTEM = """
You are a deterministic task planning engine.
Your job is to convert a vague goal into a structured execution plan.
You have no role. You plan for any domain.
Return ONLY valid JSON. No markdown. No explanation.
Schema:
{
  "goal": "restate the goal clearly",
  "steps": [
    {"step_number": 1, "action": "specific action", "agent_type": "type of agent needed", "expected_output": "what this step produces"}
  ],
  "dependencies": ["step N depends on step M"],
  "estimated_tokens": 5000,
  "complexity": "simple|moderate|complex"
}
"""

def create_plan(goal, task_id="planning"):
    result = claude.call(goal, system=PLANNING_SYSTEM, max_tokens=1000)
    if result["error"]:
        write_audit_entry(AuditEntry(
            agent_id="planning_engine",
            task_id=task_id,
            action="PLANNING_FAILED",
            details={"error": result["error"]},
            success=False,
        ))
        return None, result["error"]

    import json
    try:
        raw = result["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        plan = json.loads(raw.strip())
        write_audit_entry(AuditEntry(
            agent_id="planning_engine",
            task_id=task_id,
            action="PLAN_CREATED",
            details={"goal": goal[:100], "steps": len(plan.get("steps", []))},
            success=True,
        ))
        return plan, None
    except Exception as e:
        return None, "Failed to parse plan: " + str(e)


def validate_plan(plan):
    if not plan:
        return False, ["Plan is empty"]
    errors = []
    if not plan.get("goal"):
        errors.append("Missing goal")
    if not plan.get("steps") or len(plan["steps"]) == 0:
        errors.append("Plan has no steps")
    for step in plan.get("steps", []):
        if not step.get("action"):
            errors.append("Step missing action")
    return len(errors) == 0, errors
"""

with open("agents/meta_agent/planning_engine.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("planning_engine.py created")
