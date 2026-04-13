with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.agent_runtime import runtime"
new = """from agents.runtime.agent_runtime import runtime
from agents.meta_agent.task_gateway import gateway"""

content = content.replace(old, new)

old_create = '''    if not rate_limiter.is_allowed("founder"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait.")

    safe, reason = is_safe(body.request, agent_id="founder")
    if not safe:
        raise HTTPException(status_code=400, detail="Request blocked: " + reason)

    if not is_within_daily_budget():
        raise HTTPException(status_code=429, detail="Daily token budget exceeded.")

    task_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())'''

new_create = '''    task_envelope, errors = gateway.validate_and_admit(
        body.request, source="founder"
    )
    if errors:
        raise HTTPException(status_code=400, detail=" | ".join(errors))

    task_id = task_envelope["task_id"]
    session_id = str(uuid.uuid4())'''

content = content.replace(old_create, new_create)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with task entry gateway")
