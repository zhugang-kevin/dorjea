with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.runtime.code_executor import execute_code"
new = """from agents.runtime.code_executor import execute_code
from agents.meta_agent.auth import (load_users, save_user, save_users, get_user, create_user, verify_password, hash_password, make_token)
    get_plan_limits, check_daily_tokens, update_token_usage, PLAN_LIMITS
)
from fastapi import Header
from typing import Optional"""

content = content.replace(old, new)

content += """

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    lang: str = "en"

class LoginRequest(BaseModel):
    email: str
    password: str
    captcha_answer: int
    captcha_expected: int

@app.post("/auth/register")
def register(body: RegisterRequest, request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    user, error = register_user(body.email, body.password, body.name, ip, ua, body.lang)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "message": "Registration successful. Please login."}

@app.post("/auth/login")
def login(body: LoginRequest, request: Request) -> dict:
    if body.captcha_answer != body.captcha_expected:
        raise HTTPException(status_code=400, detail="Incorrect captcha answer.")
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    result, error = login_user(body.email, body.password, ip, ua)
    if error:
        raise HTTPException(status_code=401, detail=error)
    return {"status": "SUCCESS", "token": result["token"], "user": result["user"]}

@app.get("/auth/me")
def get_me(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    limits = get_plan_limits(user.get("plan", "free"))
    return {
        "user": {k: v for k, v in user.items() if k != "password_hash"},
        "plan_limits": limits,
        "daily_tokens_used": user.get("daily_tokens_used", 0),
        "daily_token_limit": limits["daily_tokens"],
    }

@app.get("/plans")
def get_plans() -> dict:
    return {"plans": PLAN_LIMITS}
"""

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with auth endpoints")
