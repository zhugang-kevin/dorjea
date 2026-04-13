import json
from agents.runtime.ai_clients import ClaudeClient
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

claude = ClaudeClient()

PLANNING_SYSTEM = (
    "You are a deterministic task planning engine. "
    "Convert a vague goal into a structured execution plan. "
    "You have no role. You plan for any domain. "
    "Return ONLY valid JSON. No markdown. No explanation. "
    "Schema: {goal, steps:[{step_number, action, agent_type, expected_output}], "
    "dependencies, estimated_tokens, complexity}"
)


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
