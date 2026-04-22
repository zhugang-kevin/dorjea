import time
from datetime import datetime
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry


ERROR_CATEGORIES = {
    "tool_failure": [
        "connection error", "timeout", "mcp", "server", "port"
    ],
    "model_failure": [
        "api error", "rate limit", "authentication", "forbidden",
        "llm", "大模型", "deepseek", "通义", "密钥",
    ],
    "data_error": [
        "validation", "schema", "json", "parse", "pydantic"
    ],
    "logic_error": [
        "assertion", "key error", "type error", "attribute error"
    ],
    "budget_error": [
        "token", "budget", "exceeded"
    ],
    "security_error": [
        "injection", "blocked", "sandbox", "forbidden action"
    ],
}

RECOVERY_STRATEGIES = {
    "tool_failure": "retry",
    "model_failure": "switch_model",
    "data_error": "replan",
    "logic_error": "escalate",
    "budget_error": "escalate",
    "security_error": "halt",
}


def classify_error(error_message):
    error_lower = str(error_message).lower()
    for category, keywords in ERROR_CATEGORIES.items():
        if any(kw in error_lower for kw in keywords):
            return category
    return "unknown_error"


def get_recovery_strategy(error_category):
    return RECOVERY_STRATEGIES.get(error_category, "escalate")


def execute_recovery(agent_id, task_id, error_message, retry_count=0, max_retries=3):
    category = classify_error(error_message)
    strategy = get_recovery_strategy(category)

    write_audit_entry(AuditEntry(
        agent_id=agent_id,
        task_id=task_id,
        action="ERROR_RECOVERY_TRIGGERED",
        details={
            "error_category": category,
            "strategy": strategy,
            "retry_count": retry_count,
            "error_preview": str(error_message)[:200],
        },
        success=False,
    ))

    if strategy == "halt" or category == "security_error":
        return {
            "action": "halt",
            "reason": "Security violation — system halted",
            "should_retry": False,
            "should_escalate": True,
        }

    if strategy == "retry" and retry_count < max_retries:
        wait_seconds = 2 ** retry_count
        time.sleep(wait_seconds)
        return {
            "action": "retry",
            "reason": "Tool failure — retrying after " + str(wait_seconds) + "s",
            "should_retry": True,
            "should_escalate": False,
            "wait_seconds": wait_seconds,
        }

    if strategy == "switch_model":
        import os
        fallback = os.getenv("VERIFIER_MODEL", "gpt-4o")
        return {
            "action": "switch_model",
            "reason": "Model failure — switching to fallback: " + fallback,
            "should_retry": True,
            "should_escalate": False,
            "fallback_model": fallback,
        }

    if strategy == "replan" or retry_count >= max_retries:
        return {
            "action": "escalate",
            "reason": "Max retries exceeded or unrecoverable error — escalating to founder",
            "should_retry": False,
            "should_escalate": True,
        }

    return {
        "action": "escalate",
        "reason": "Unknown error category — escalating to founder",
        "should_retry": False,
        "should_escalate": True,
    }


def should_escalate_to_founder(error_category, retry_count, max_retries=3):
    if error_category in ("security_error", "logic_error", "budget_error"):
        return True
    if retry_count >= max_retries:
        return True
    return False