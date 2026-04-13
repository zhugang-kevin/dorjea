with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.ai_clients import ClaudeClient, OpenAIClient"
new = "from agents.runtime.ai_clients import ClaudeClient, OpenAIClient\nfrom agents.runtime.model_router import call_with_fallback as routed_call"

content = content.replace(old, new)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with model router import")
