with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add self-defence imports after existing imports
old_import = "from agents.runtime.ai_clients import ClaudeClient, OpenAIClient"
new_import = """from agents.runtime.ai_clients import ClaudeClient, OpenAIClient
from self_defence.injection_detector import is_safe
from self_defence.rate_limiter import rate_limiter"""

content = content.replace(old_import, new_import)

# Add defence check at start of parse_request node
old_parse = '''    founder_request = state.get("founder_request", "")
    if not founder_request:
        _audit(state, "parse_request", "Empty founder request", success=False)
        return {
            "current_error": "Founder request is empty.",
            "should_stop": True,
        }'''

new_parse = '''    founder_request = state.get("founder_request", "")
    if not founder_request:
        _audit(state, "parse_request", "Empty founder request", success=False)
        return {
            "current_error": "Founder request is empty.",
            "should_stop": True,
        }

    safe, reason = is_safe(founder_request, agent_id=state.get("task_id", "system"))
    if not safe:
        _audit(state, "parse_request", "Injection blocked: " + reason, success=False)
        return {
            "current_error": "Request blocked by security filter: " + reason,
            "should_stop": True,
        }

    if not rate_limiter.wait_if_needed("meta_agent", timeout=3.0):
        _audit(state, "parse_request", "Rate limit exceeded", success=False)
        return {
            "current_error": "Rate limit exceeded. Please wait before submitting again.",
            "should_stop": True,
        }'''

content = content.replace(old_parse, new_parse)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with Self-Defence")
