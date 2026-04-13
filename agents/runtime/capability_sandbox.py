from agents.meta_agent.manifest_manager import load_manifest, check_tool_permitted, check_action_permitted
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry


class CapabilitySandbox:
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.manifest = load_manifest(agent_name)

    def is_tool_allowed(self, tool_name):
        if not self.manifest:
            return False, "No manifest found for agent: " + self.agent_name
        permitted, reason = check_tool_permitted(self.agent_name, tool_name)
        if not permitted:
            write_audit_entry(AuditEntry(
                agent_id=self.agent_name,
                task_id="sandbox",
                action="TOOL_BLOCKED_BY_SANDBOX",
                details={"tool": tool_name, "reason": reason},
                success=False,
            ))
        return permitted, reason

    def is_action_allowed(self, action):
        if not self.manifest:
            return False, "No manifest found for agent: " + self.agent_name
        permitted, reason = check_action_permitted(self.agent_name, action)
        if not permitted:
            write_audit_entry(AuditEntry(
                agent_id=self.agent_name,
                task_id="sandbox",
                action="ACTION_BLOCKED_BY_SANDBOX",
                details={"action": action[:100], "reason": reason},
                success=False,
            ))
        return permitted, reason

    def get_allowed_tools(self):
        if not self.manifest:
            return []
        return self.manifest.get("permissions", {}).get("allowed_tools", [])

    def get_resource_limits(self):
        if not self.manifest:
            return {"max_tokens_per_task": 5000, "max_runtime_seconds": 120}
        return self.manifest.get("resource_limits", {})

    def can_create_agents(self):
        if not self.manifest:
            return False
        return self.manifest.get("governance", {}).get("can_create_agents", False)

    def can_modify_core(self):
        if not self.manifest:
            return False
        return self.manifest.get("governance", {}).get("can_modify_core", False)


def create_sandbox(agent_name):
    return CapabilitySandbox(agent_name)