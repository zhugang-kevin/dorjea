with open("agents/meta_agent/registry.py", "r", encoding="utf-8") as f:
    content = f.read()

if "_enrich_agent" not in content:
    print("Function not found - need to add it")
else:
    print("Function exists - fixing it")
    old = """def _enrich_agent(agent: dict) -> dict:
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
    return agent"""

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
                    if agent.get(field) in (None, "", "general") and spec.get(field):
                        agent[field] = spec[field]
        except Exception:
            pass
    return agent"""

    content = content.replace(old, new)

    with open("agents/meta_agent/registry.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed")
