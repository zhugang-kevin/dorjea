code = '''
import json
import os
from fastapi import HTTPException

PLAN_LIMITS = {
    "free":         {"daily_tokens": 5000,   "max_agents": 3,   "max_clones": 0,  "price_usd": 0,  "trial_days": 3},
    "professional": {"daily_tokens": 50000,  "max_agents": 20,  "max_clones": 1,  "price_usd": 29},
    "business":     {"daily_tokens": 250000, "max_agents": 100, "max_clones": 3,  "price_usd": 99},
    "enterprise":   {"daily_tokens": 1000000,"max_agents": 500, "max_clones": 10, "price_usd": 0, "custom": True},
}

USERS_FILE = "memory/users.jsonl"
AGENTS_FILE = "memory/agents.jsonl"
CLONES_FILE = "memory/department_clones.jsonl"

def load_user(email: str):
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                u = json.loads(line)
                if u.get("email") == email:
                    return u
    return None

def get_user_plan(email: str) -> str:
    user = load_user(email)
    if not user:
        return "free"
    return user.get("plan", "free")

def get_plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

def count_user_agents(email: str) -> int:
    if not os.path.exists(AGENTS_FILE):
        return 0
    with open(AGENTS_FILE, encoding="utf-8") as f:
        agents = [json.loads(l) for l in f if l.strip()]
    return len([a for a in agents
                if a.get("user_email") == email
                and a.get("status") != "retired"
                and not a.get("deleted")])

def count_user_clones(email: str) -> int:
    if not os.path.exists(CLONES_FILE):
        return 0
    with open(CLONES_FILE, encoding="utf-8") as f:
        clones = [json.loads(l) for l in f if l.strip()]
    return len([c for c in clones
                if c.get("user_email") == email
                and not c.get("deleted")])

def enforce_agent_limit(email: str):
    plan = get_user_plan(email)
    limits = get_plan_limits(plan)
    current = count_user_agents(email)
    max_allowed = limits["max_agents"]
    if current >= max_allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Agent limit reached. Your {plan} plan allows {max_allowed} agents. "
                   f"You have {current}. Upgrade at dorjea.com/payment"
        )

def enforce_clone_limit(email: str):
    plan = get_user_plan(email)
    limits = get_plan_limits(plan)
    current = count_user_clones(email)
    max_allowed = limits["max_clones"]
    if max_allowed == 0:
        raise HTTPException(
            status_code=403,
            detail=f"Department clones are not available on the {plan} plan. "
                   f"Upgrade to Professional or higher at dorjea.com/payment"
        )
    if current >= max_allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Clone limit reached. Your {plan} plan allows {max_allowed} clones. "
                   f"You have {current}. Upgrade at dorjea.com/payment"
        )

def enforce_token_budget(email: str, tokens_requested: int):
    plan = get_user_plan(email)
    limits = get_plan_limits(plan)
    daily_limit = limits["daily_tokens"]
    # Check current usage from budget tracker
    try:
        from agents.meta_agent.api import get_budget_status
        status = get_budget_status()
        used = status.get("tokens_used", 0)
        remaining = daily_limit - used
        if tokens_requested > remaining:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token budget exceeded. Your {plan} plan allows "
                       f"{daily_limit:,} tokens/day. {remaining:,} remaining. "
                       f"Resets at midnight UTC."
            )
    except ImportError:
        pass

def check_feature_access(email: str, feature: str):
    plan = get_user_plan(email)
    feature_plans = {
        "api_keys":    ["professional", "business", "enterprise"],
        "clones":      ["professional", "business", "enterprise"],
        "workflows":   ["professional", "business", "enterprise"],
        "analytics":   ["professional", "business", "enterprise"],
        "support":     ["free", "professional", "business", "enterprise"],
    }
    allowed_plans = feature_plans.get(feature, ["free", "professional", "business", "enterprise"])
    if plan not in allowed_plans:
        raise HTTPException(
            status_code=403,
            detail=f"The {feature} feature requires a Professional plan or higher. "
                   f"Upgrade at dorjea.com/payment"
        )

def get_plan_info(email: str) -> dict:
    plan = get_user_plan(email)
    limits = get_plan_limits(plan)
    return {
        "plan": plan,
        "limits": limits,
        "usage": {
            "agents": count_user_agents(email),
            "clones": count_user_clones(email),
        },
        "remaining": {
            "agents": limits["max_agents"] - count_user_agents(email),
            "clones": limits["max_clones"] - count_user_clones(email),
        }
    }
'''

with open("agents/meta_agent/plan_enforcement.py", "w", encoding="utf-8") as f:
    f.write(code.strip())
print("plan_enforcement.py created")
