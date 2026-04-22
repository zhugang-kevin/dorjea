with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from self_governance.policy_engine import policy_engine"
new = """from self_governance.policy_engine import policy_engine
from agents.runtime.capability_sandbox import create_sandbox"""

content = content.replace(old, new)

old_safe = '''        safe, reason = is_safe(task_instruction, agent_id=agent_name)
        if not safe:
            self._log(agent_name, task_id, "TASK_BLOCKED", {"reason": reason}, success=False)
            return {
                "status": "FAILED",
                "error": "Task blocked by security filter: " + reason,
                "task_id": task_id,
            }'''

new_safe = '''        safe, reason = is_safe(task_instruction, agent_id=agent_name)
        if not safe:
            self._log(agent_name, task_id, "TASK_BLOCKED", {"reason": reason}, success=False)
            return {
                "status": "FAILED",
                "error": "Task blocked by security filter: " + reason,
                "task_id": task_id,
            }

        sandbox = create_sandbox(agent_name)
        limits = sandbox.get_resource_limits()
        token_budget = limits.get("max_tokens_per_task", agent.get("token_budget", 10000))

        if sandbox.can_create_agents():
            pass
        if sandbox.can_modify_core():
            self._log(agent_name, task_id, "SANDBOX_VIOLATION",
                     {"reason": "Agent attempted core modification"}, success=False)
            return {
                "status": "FAILED",
                "error": "Sandbox violation: agent cannot modify core system.",
                "task_id": task_id,
            }'''

content = content.replace(old_safe, new_safe)

old_budget = "        token_budget = agent.get(\"token_budget\", 10000)"
content = content.replace(old_budget, "        token_budget = agent.get(\"token_budget\", token_budget)")

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.write(content)
print("agent_runtime.py updated with capability sandbox")
