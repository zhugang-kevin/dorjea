with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    lines = f.readlines()

# Find line 96 (index 95) and the function body start
for i, line in enumerate(lines):
    if '@app.post("/agents/create"' in line:
        print(f"Found at line {i+1}")
        # Print next 10 lines to see function signature
        for j in range(i, min(i+10, len(lines))):
            print(str(j+1)+":", lines[j].rstrip())
        break
