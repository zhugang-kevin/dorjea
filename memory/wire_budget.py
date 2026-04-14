with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

content += """

class BudgetConfig(BaseModel):
    daily_budget: int

@app.post("/system/budget")
def set_budget(body: BudgetConfig) -> dict:
    import os
    env_path = ".env"
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("DAILY_TOKEN_BUDGET="):
            new_lines.append("DAILY_TOKEN_BUDGET=" + str(body.daily_budget) + chr(10))
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append("DAILY_TOKEN_BUDGET=" + str(body.daily_budget) + chr(10))
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.environ["DAILY_TOKEN_BUDGET"] = str(body.daily_budget)
    return {"status": "SUCCESS", "daily_budget": body.daily_budget}

@app.get("/system/budget")
def get_budget() -> dict:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    budget = int(os.getenv("DAILY_TOKEN_BUDGET", "100000"))
    used = get_daily_usage()
    return {
        "daily_budget": budget,
        "tokens_used": used,
        "tokens_remaining": max(0, budget - used),
        "usage_percent": round(used / budget * 100, 1) if budget > 0 else 0,
    }
"""

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with budget endpoints")
