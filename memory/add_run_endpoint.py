with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from self_token.budget_manager import get_daily_usage, is_within_daily_budget"
new = """from self_token.budget_manager import get_daily_usage, is_within_daily_budget
from agents.runtime.agent_runtime import runtime"""

content = content.replace(old, new)

old_end = """@app.get("/metrics")
def get_metrics() -> dict:
    return {
        "daily_tokens_used": get_daily_usage(),
        "daily_budget": 50000,
        "budget_remaining": 50000 - get_daily_usage(),
        "budget_ok": is_within_daily_budget(),
    }"""

new_end = """@app.get("/metrics")
def get_metrics() -> dict:
    return {
        "daily_tokens_used": get_daily_usage(),
        "daily_budget": 50000,
        "budget_remaining": 50000 - get_daily_usage(),
        "budget_ok": is_within_daily_budget(),
    }


class RunTaskRequest(BaseModel):
    task: str


@app.post("/agents/{agent_name}/run")
def run_agent_task(agent_name: str, body: RunTaskRequest) -> dict:
    if not body.task or len(body.task.strip()) < 5:
        raise HTTPException(status_code=400, detail="Task must be at least 5 characters.")
    if not rate_limiter.is_allowed("founder"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    safe, reason = is_safe(body.task, agent_id="founder")
    if not safe:
        raise HTTPException(status_code=400, detail="Task blocked: " + reason)
    result = runtime.run_task(agent_name, body.task)
    if result["status"] == "FAILED":
        raise HTTPException(status_code=400, detail=result.get("error", "Task failed"))
    return result"""

content = content.replace(old_end, new_end)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with /agents/{name}/run endpoint")
