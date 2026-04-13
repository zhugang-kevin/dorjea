with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def generate_spec" in line:
        for j in range(i, min(i+55, len(lines))):
            print(str(j+1) + ": " + lines[j], end="")
        break
