with open("agents/runtime/agent_runtime.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

fixed = []
for line in lines:
    if 'code_blocks = re.findall' in line:
        fixed.append('            code_blocks = re.findall(r"\\`\\`\\`(?:python)?\\n?(.*?)\\`\\`\\`", output_text, re.DOTALL)\n')
    else:
        fixed.append(line)

with open("agents/runtime/agent_runtime.py", "w", encoding="utf-8") as f:
    f.writelines(fixed)
print("fixed")
