content = """
import os
import yaml
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry


class PolicyEngine:
    def __init__(self, policy_path="agents/meta_agent/policy.yaml"):
        with open(policy_path, "r", encoding="utf-8") as f:
            self.policy = yaml.safe_load(f)

    def get_token_budget(self, task_type="default"):
        budgets = self.policy.get("token_budgets", {})
        return budgets.get(task_type, budgets.get("default", 20000))

    def get_retry_policy(self):
        return self.policy.get("retry_policy", {"max_attempts": 3, "backoff_seconds": 2})

    def check_tool_allowed(self, agent_id, tool_name, agent_allowed_tools):
        if tool_name not in agent_allowed_tools:
            write_audit_entry(AuditEntry(
                agent_id=agent_id, task_id="system",
                action="TOOL_BLOCKED",
                details={"tool": tool_name, "reason": "not in allowed_tools"},
                success=False
            ))
            return False
        return True

    def check_forbidden_action(self, agent_id, action):
        forbidden = self.policy.get("safety", {}).get("forbidden_packages", [])
        for f in forbidden:
            if f.lower() in action.lower():
                write_audit_entry(AuditEntry(
                    agent_id=agent_id, task_id="system",
                    action="FORBIDDEN_ACTION_BLOCKED",
                    details={"action": action, "matched": f},
                    success=False
                ))
                return False
        return True

    def get_model(self, tier="primary"):
        routing = self.policy.get("model_routing", {})
        tier_model = routing.get(tier, "primary")
        if tier_model == "primary":
            return os.getenv("PRIMARY_MODEL", "claude-sonnet-4-6")
        elif tier_model == "verifier":
            return os.getenv("VERIFIER_MODEL", "gpt-4o")
        elif tier_model == "heavy":
            return os.getenv("HEAVY_MODEL", "claude-opus-4-6")
        return os.getenv("PRIMARY_MODEL", "claude-sonnet-4-6")

    def should_halt_on_budget(self):
        return self.policy.get("retry_policy", {}).get("halt_on_budget_exceeded", True)


policy_engine = PolicyEngine()
"""

with open("self_governance/policy_engine.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("policy_engine.py created")
