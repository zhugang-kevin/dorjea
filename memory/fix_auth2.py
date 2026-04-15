with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add auth import after load_dotenv line
old = "load_dotenv()"
new = """load_dotenv()

from agents.meta_agent.auth import (
    register_user, login_user, get_user_by_token,
    get_plan_limits, PLAN_LIMITS
)"""

content = content.replace(old, new, 1)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
