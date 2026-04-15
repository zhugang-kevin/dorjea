with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.code_executor import execute_code"
new = """from agents.runtime.code_executor import execute_code
from agents.meta_agent.auth import (
    register_user, login_user, get_user_by_token,
    get_plan_limits, check_daily_tokens, update_token_usage, PLAN_LIMITS
)
from typing import Optional"""

content = content.replace(old, new)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("auth import added")
