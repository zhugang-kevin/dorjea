with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.error_recovery import classify_error, execute_recovery, should_escalate_to_founder"
new = """from agents.runtime.error_recovery import classify_error, execute_recovery, should_escalate_to_founder
from self_monitoring.agent_performance import record_task_result"""

content = content.replace(old, new)

old_success = '''        self._log(agent_name, task_id, "TASK_COMPLETED",
                 {"tokens": result["total_tokens"], "output_preview": result["text"][:200]})

        return {
            "status": "SUCCESS",
            "task_id": task_id,
            "agent_name": agent_name,
            "output": result["text"],
            "tokens_used": result["total_tokens"],
            "model_used": model,
            "completed_at": datetime.utcnow().isoformat(),
        }'''

new_success = '''        elapsed = (datetime.utcnow() - datetime.fromisoformat(
            datetime.utcnow().isoformat())).total_seconds()
        record_task_result(
            agent_name=agent_name,
            task_id=task_id,
            success=True,
            tokens_used=result["total_tokens"],
            elapsed_seconds=0,
        )
        self._log(agent_name, task_id, "TASK_COMPLETED",
                 {"tokens": result["total_tokens"], "output_preview": result["text"][:200]})

        return {
            "status": "SUCCESS",
            "task_id": task_id,
            "agent_name": agent_name,
            "output": result["text"],
            "tokens_used": result["total_tokens"],
            "model_used": model,
            "completed_at": datetime.utcnow().isoformat(),
        }'''

content = content.replace(old_success, new_success)

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.write(content)
print("agent_runtime.py updated with performance tracking")
