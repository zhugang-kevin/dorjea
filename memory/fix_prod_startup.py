with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "load_dotenv()"
new = """load_dotenv()
import os
# Ensure critical env vars have defaults for production startup
if not os.getenv("PRIMARY_MODEL"):
    os.environ["PRIMARY_MODEL"] = "claude-sonnet-4-6"
if not os.getenv("DAILY_TOKEN_BUDGET"):
    os.environ["DAILY_TOKEN_BUDGET"] = "100000"
if not os.getenv("JWT_SECRET_KEY"):
    import secrets
    os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)"""

content = content.replace(old, new, 1)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("API startup fixed for production")
