with open("agents/meta_agent/registry.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def get_agent(agent_name: str) -> Optional[dict]:"
new = """def _enrich_agent(agent: dict) -> dict:
    if not agent:
        return agent
    spec_yaml = agent.get("spec_yaml", "")
    if spec_yaml:
        try:
            import yaml
            spec = yaml.safe_load(spec_yaml)
            if spec:
                for field in ["department", "responsibilities", "non_responsibilities",
                              "escalation_triggers", "memory_policy", "retry_policy"]:
                    if not agent.get(field) and spec.get(field):
                        agent[field] = spec[field]
        except Exception:
            pass
    return agent

def get_agent(agent_name: str) -> Optional[dict]:"""

content = content.replace(old, new)

old_return = '''    row = _fetchone(cursor)
        conn.close()
        return row'''
new_return = '''    row = _fetchone(cursor)
        conn.close()
        return _enrich_agent(row)'''
content = content.replace(old_return, new_return)

old_list = "return [dict(row) for row in rows]"
new_list = "return [_enrich_agent(dict(row) if not isinstance(row, dict) else row) for row in rows]"
content = content.replace(old_list, new_list)

with open("agents/meta_agent/registry.py", "w", encoding="utf-8") as f:
    f.write(content)
print("registry.py updated — department enriched from spec_yaml")
