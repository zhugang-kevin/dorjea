with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.version_checker import check_all_versions"
new = "from agents.meta_agent.version_checker import check_all_versions\nfrom agents.meta_agent.agent_auditor import audit_all_agents"

content = content.replace(old, new)

content += """

@app.get("/agents/audit")
def audit_agents() -> dict:
    return audit_all_agents()
"""

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with audit endpoint")
