with open("agents/meta_agent/auth.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """PLAN_LIMITS = {
    "free":         {"daily_tokens": 10000,  "max_agents": 3,   "max_clones": 0, "price_usd": 0,   "price_cny": 0},
    "professional": {"daily_tokens": 100000, "max_agents": 20,  "max_clones": 1, "price_usd": 49,  "price_cny": 349},
    "business":     {"daily_tokens": 500000, "max_agents": 100, "max_clones": 5, "price_usd": 199, "price_cny": 1399},
    "enterprise":   {"daily_tokens": 999999, "max_agents": 999, "max_clones": 99,"price_usd": 999, "price_cny": 6999},
}"""

new = """PLAN_LIMITS = {
    "free":         {"daily_tokens": 5000,   "max_agents": 3,   "max_clones": 0, "price_usd": 0,   "trial_days": 3},
    "professional": {"daily_tokens": 50000,  "max_agents": 20,  "max_clones": 1, "price_usd": 29},
    "business":     {"daily_tokens": 250000, "max_agents": 100, "max_clones": 3, "price_usd": 99},
    "enterprise":   {"daily_tokens": 1000000,"max_agents": 500, "max_clones": 10,"price_usd": 0, "custom": True},
}"""

content = content.replace(old, new)
with open("agents/meta_agent/auth.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Plan limits updated")
