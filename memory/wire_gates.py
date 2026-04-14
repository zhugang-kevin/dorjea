with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.architecture_validator import run_full_architecture_validation"
new = """from agents.meta_agent.architecture_validator import run_full_architecture_validation
from agents.meta_agent.validation_gates import run_all_validation_gates"""

content = content.replace(old, new)

old_arch = '''    arch_ok, arch_errors = run_full_architecture_validation(agent_spec)
    if not arch_ok:
        error_msg = "Architecture validation failed: " + " | ".join(arch_errors)
        _audit(state, "register_agent", error_msg, success=False)
        return {
            "current_error": error_msg,
            "should_stop": True,
        }
    _audit(state, "register_agent", "Architecture validation passed")'''

new_arch = '''    arch_ok, arch_errors = run_full_architecture_validation(agent_spec)
    if not arch_ok:
        error_msg = "Architecture validation failed: " + " | ".join(arch_errors)
        _audit(state, "register_agent", error_msg, success=False)
        return {"current_error": error_msg, "should_stop": True}
    _audit(state, "register_agent", "Architecture validation passed")

    gates_result = run_all_validation_gates(agent_spec)
    _audit(state, "register_agent",
           "Validation gates: " + str(gates_result["gates_passed"]) + "/" + str(gates_result["total_gates"]) + " passed",
           success=gates_result["passed"])
    if not gates_result["passed"]:
        error_msg = "Validation gates failed: " + " | ".join(gates_result["errors"][:3])
        return {"current_error": error_msg, "should_stop": True}'''

content = content.replace(old_arch, new_arch)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with all 10 validation gates")
