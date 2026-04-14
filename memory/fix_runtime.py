with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "code_execution_result = None" in line:
        skip = True
        new_lines.append("        code_execution_result = None\n")
        new_lines.append("        output_text = result['text']\n")
    elif skip and "self._log(agent_name, task_id, \"TASK_COMPLETED\"" in line:
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("fixed")
