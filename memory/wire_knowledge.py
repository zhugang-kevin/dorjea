with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.lifecycle_manager import transition_agent, get_lifecycle_summary, get_lifecycle_history"
new = """from agents.meta_agent.lifecycle_manager import transition_agent, get_lifecycle_summary, get_lifecycle_history
from agents.meta_agent.communication_protocol import send_message, get_messages
from agents.meta_agent.knowledge_consistency import get_knowledge_summary, check_consistency"""

content = content.replace(old, new)

content += """

@app.get("/system/knowledge")
def knowledge_summary() -> dict:
    return get_knowledge_summary()

@app.get("/system/knowledge/consistency")
def knowledge_consistency() -> dict:
    return check_consistency()
"""

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with knowledge endpoints")
