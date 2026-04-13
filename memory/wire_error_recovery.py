with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.capability_sandbox import create_sandbox"
new = """from agents.runtime.capability_sandbox import create_sandbox
from agents.runtime.error_recovery import classify_error, execute_recovery, should_escalate_to_founder"""

content = content.replace(old, new)

old_error = '''        if result["error"]:
            self._log(agent_name, task_id, "TASK_FAILED",
                     {"error": result["error"]}, success=False)
            return {
                "status": "FAILED",
                "error": result["error"],
                "task_id": task_id,
                "agent_name": agent_name,
                "tokens_used": 0,
            }'''

new_error = '''        if result["error"]:
            recovery = execute_recovery(
                agent_id=agent_name,
                task_id=task_id,
                error_message=result["error"],
                retry_count=0,
            )
            self._log(agent_name, task_id, "TASK_FAILED",
                     {"error": result["error"],
                      "recovery_action": recovery["action"]}, success=False)
            return {
                "status": "FAILED",
                "error": result["error"],
                "task_id": task_id,
                "agent_name": agent_name,
                "tokens_used": 0,
                "recovery_action": recovery["action"],
                "escalate_to_founder": recovery["should_escalate"],
            }'''

content = content.replace(old_error, new_error)

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.write(content)
print("agent_runtime.py updated with error recovery loop")
