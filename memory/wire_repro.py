with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.architecture_validator import run_full_architecture_validation"
new = """from agents.meta_agent.architecture_validator import run_full_architecture_validation
from agents.meta_agent.reproducibility import save_execution_record"""

content = content.replace(old, new)

# Wire into generate_spec after the claude.call
old_gen_call = '''    result = claude.call(
        build_generate_spec_user_message(task_spec, []),
        system=GENERATE_SPEC_SYSTEM,
        max_tokens=2000,
    )
    if result["error"]:
        _audit(state, "generate_spec", f"Claude error: {result[\'error\']}", success=False)'''

new_gen_call = '''    user_msg = build_generate_spec_user_message(task_spec, [])
    result = claude.call(
        user_msg,
        system=GENERATE_SPEC_SYSTEM,
        max_tokens=2000,
    )
    save_execution_record(
        task_id=state.get("task_id", "unknown"),
        agent_id=task_spec.agent_name,
        node_name="generate_spec",
        model=claude.model,
        system_prompt=GENERATE_SPEC_SYSTEM,
        user_prompt=user_msg,
        output=result.get("text", ""),
        tokens_used=result.get("total_tokens", 0),
    )
    if result["error"]:
        _audit(state, "generate_spec", f"Claude error: {result[\'error\']}", success=False)'''

content = content.replace(old_gen_call, new_gen_call)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with reproducibility recording")
