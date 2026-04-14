with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "        code_execution_result = None\n        output_text = result['text']"
new = """        code_execution_result = None
        output_text = result["text"]
        task_lower = task_instruction.lower()
        if "run this code" in task_lower or "execute this" in task_lower or "test this code" in task_lower:
            tick3 = chr(96) * 3
            start_idx = output_text.find(tick3)
            if start_idx >= 0:
                end_idx = output_text.find(tick3, start_idx + 3)
                if end_idx > start_idx:
                    code_block = output_text[start_idx+3:end_idx].strip()
                    if code_block.startswith("python"):
                        code_block = code_block[6:].strip()
                    exec_result = execute_code(agent_name, task_id, code_block)
                    code_execution_result = exec_result
                    if exec_result["success"]:
                        output_text += chr(10) + chr(10) + "Execution Result:" + chr(10) + exec_result["output"]
                    else:
                        output_text += chr(10) + chr(10) + "Execution Error:" + chr(10) + exec_result["error"]"""

content = content.replace(old, new)

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.write(content)
print("agent_runtime.py updated with safe code execution")
