with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.error_recovery import classify_error, execute_recovery, should_escalate_to_founder"
new = """from agents.runtime.error_recovery import classify_error, execute_recovery, should_escalate_to_founder
from agents.runtime.code_executor import execute_code, run_tests"""

content = content.replace(old, new)

old_success = '''        self._log(agent_name, task_id, "TASK_COMPLETED",
                 {"tokens": result["total_tokens"], "output_preview": result["text"][:200]})'''

new_success = '''        output_text = result["text"]

        code_execution_result = None
        if any(kw in task_instruction.lower() for kw in ["run this code", "execute this", "test this code", "run the code"]):
            import re
            code_blocks = re.findall(r"```(?:python)?\n?(.*?)```", output_text, re.DOTALL)
            if code_blocks:
                exec_result = execute_code(agent_name, task_id, code_blocks[0])
                code_execution_result = exec_result
                if exec_result["success"]:
                    output_text += chr(10) + chr(10) + "**Code Execution Result:**" + chr(10) + exec_result["output"]
                else:
                    output_text += chr(10) + chr(10) + "**Execution Error:**" + chr(10) + exec_result["error"]

        self._log(agent_name, task_id, "TASK_COMPLETED",
                 {"tokens": result["total_tokens"], "output_preview": result["text"][:200]})'''

content = content.replace(old_success, new_success)

old_return = '''        return {
            "status": "SUCCESS",
            "task_id": task_id,
            "agent_name": agent_name,
            "output": result["text"],
            "tokens_used": result["total_tokens"],
            "model_used": model,
            "completed_at": datetime.utcnow().isoformat(),
        }'''

new_return = '''        return {
            "status": "SUCCESS",
            "task_id": task_id,
            "agent_name": agent_name,
            "output": output_text,
            "tokens_used": result["total_tokens"],
            "model_used": model,
            "completed_at": datetime.utcnow().isoformat(),
            "code_execution": code_execution_result,
        }'''

content = content.replace(old_return, new_return)

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.write(content)
print("agent_runtime.py updated with code execution")
