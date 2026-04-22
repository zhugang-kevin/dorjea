"""任务规划引擎：将目标转为结构化执行计划（境内主模型）。"""
import json

from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from agents.runtime.ai_clients import AIChatRequest, PrimaryChatClient
from agents.runtime.reliability import ReliabilityPolicy, call_with_reliability

primary_llm = PrimaryChatClient()

PLANNING_SYSTEM = (
    "You are a deterministic task planning engine. "
    "Convert a vague goal into a structured execution plan. "
    "You have no role. You plan for any domain. "
    "Return ONLY valid JSON. No markdown. No explanation. "
    "Schema: {goal, steps:[{step_number, action, agent_type, expected_output}], "
    "dependencies, estimated_tokens, complexity}"
)


def create_plan(goal, task_id="planning"):
    """
    调用主模型生成计划 JSON。

    返回 (plan_dict, error_str)；成功时 error_str 为 None。
    """
    try:
        req = AIChatRequest(prompt=goal, system=PLANNING_SYSTEM, max_tokens=1000)
        reliable = call_with_reliability(
            request=req,
            task_id=task_id,
            agent_id="planning_engine",
            client=primary_llm,
            policy=ReliabilityPolicy(require_json=True, min_output_chars=32, min_confidence=0.6),
        )
        result = reliable.response
    except Exception as exc:
        err = f"规划请求异常：{exc!s}"
        write_audit_entry(
            AuditEntry(
                agent_id="planning_engine",
                task_id=task_id,
                action="PLANNING_FAILED",
                details={"error": err},
                success=False,
            )
        )
        return None, err
    if result.error:
        write_audit_entry(
            AuditEntry(
                agent_id="planning_engine",
                task_id=task_id,
                action="PLANNING_FAILED",
                details={"error": result.error},
                success=False,
            )
        )
        return None, result.error
    try:
        raw = result.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        plan = json.loads(raw.strip())
        write_audit_entry(
            AuditEntry(
                agent_id="planning_engine",
                task_id=task_id,
                action="PLAN_CREATED",
                details={"goal": goal[:100], "steps": len(plan.get("steps", []))},
                success=True,
            )
        )
        return plan, None
    except Exception as e:
        return None, "Failed to parse plan: " + str(e)


def validate_plan(plan):
    """
    校验计划结构是否包含目标与步骤。

    返回 (is_valid, error_messages)。
    """
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
