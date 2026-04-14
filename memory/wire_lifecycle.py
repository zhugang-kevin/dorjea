with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.agent_auditor import audit_all_agents"
new = """from agents.meta_agent.agent_auditor import audit_all_agents
from agents.meta_agent.lifecycle_manager import transition_agent, get_lifecycle_summary, get_lifecycle_history"""

content = content.replace(old, new)

content += """

@app.get("/agents/lifecycle")
def lifecycle_summary() -> dict:
    return get_lifecycle_summary()

@app.get("/agents/{agent_name}/lifecycle")
def agent_lifecycle_history(agent_name: str) -> dict:
    return {"agent": agent_name, "history": get_lifecycle_history(agent_name)}

@app.post("/agents/{agent_name}/deploy")
def deploy_agent_endpoint(agent_name: str) -> dict:
    ok, msg = transition_agent(agent_name, "deployed", "Deployed via API")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}

@app.post("/agents/{agent_name}/retire")
def retire_agent_endpoint(agent_name: str) -> dict:
    ok, msg = transition_agent(agent_name, "retired", "Retired via API")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}
"""

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with lifecycle endpoints")
