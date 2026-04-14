with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''        raw = result["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        agent_spec = AgentSpec(**data)'''

new = '''        raw = result["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        brace_start = raw.find("{")
        brace_end = raw.rfind("}") + 1
        if brace_start >= 0 and brace_end > brace_start:
            raw = raw[brace_start:brace_end]
        data = json.loads(raw)
        agent_spec = AgentSpec(**data)'''

content = content.replace(old, new)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("JSON parser fixed in generate_spec")
