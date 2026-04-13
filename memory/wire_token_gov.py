with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old_import = "from self_defence.injection_detector import is_safe"
new_import = """from self_defence.injection_detector import is_safe
from self_token.budget_manager import track_tokens, is_within_budget
from self_governance.policy_engine import policy_engine"""

content = content.replace(old_import, new_import)

old_claude_call = '''    result = claude.call(prompt, system=system)
    if result["error"]:
        _audit(state, "parse_request", f"Claude error: {result['error']}", success=False)'''

new_claude_call = '''    if not is_within_budget(state.get("total_tokens_used", 0)):
        _audit(state, "parse_request", "Token budget exceeded", success=False)
        return {
            "current_error": "Token budget exceeded for this task.",
            "should_stop": True,
        }

    result = claude.call(prompt, system=system)
    if result["error"]:
        _audit(state, "parse_request", f"Claude error: {result['error']}", success=False)'''

content = content.replace(old_claude_call, new_claude_call)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with Self-Token and Self-Governance")
