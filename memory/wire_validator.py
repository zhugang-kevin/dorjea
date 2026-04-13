with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.manifest_manager import save_manifest"
new = """from agents.meta_agent.manifest_manager import save_manifest
from agents.meta_agent.architecture_validator import run_full_architecture_validation"""

content = content.replace(old, new)

old_register_start = '''def register_agent(state: MetaAgentState) -> dict:
    """
    Node 8: Register the verified and tested agent in the database.
    Saves the agent spec YAML to agents/specs/ folder.
    """
    if state.get("should_stop"):
        return {}

    agent_spec = state.get("agent_spec")
    spec_yaml = state.get("generated_spec_yaml", "")
    if not agent_spec:
        return {"current_error": "No AgentSpec to register.", "should_stop": True}'''

new_register_start = '''def register_agent(state: MetaAgentState) -> dict:
    """
    Node 8: Run architecture validation then register the agent in the database.
    Validates spec, generated files, and manifest before registration.
    """
    if state.get("should_stop"):
        return {}

    agent_spec = state.get("agent_spec")
    spec_yaml = state.get("generated_spec_yaml", "")
    if not agent_spec:
        return {"current_error": "No AgentSpec to register.", "should_stop": True}

    arch_ok, arch_errors = run_full_architecture_validation(agent_spec)
    if not arch_ok:
        error_msg = "Architecture validation failed: " + " | ".join(arch_errors)
        _audit(state, "register_agent", error_msg, success=False)
        return {
            "current_error": error_msg,
            "should_stop": True,
        }
    _audit(state, "register_agent", "Architecture validation passed")'''

content = content.replace(old_register_start, new_register_start)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with architecture validation gate")
