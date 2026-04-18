with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

# Add import
if "plan_enforcement" not in content:
    content = content.replace(
        "from agents.meta_agent.clones import router as clones_router",
        "from agents.meta_agent.clones import router as clones_router\nfrom agents.meta_agent.plan_enforcement import enforce_agent_limit, enforce_clone_limit, check_feature_access"
    )

# Find agent creation endpoint and add enforcement
# Look for the create agent endpoint
old = '@app.post("/agents/create")'
if old in content:
    # Find the function body and add enforcement
    idx = content.find(old)
    func_start = content.find("def ", idx)
    func_body_start = content.find(":", func_start) + 1
    # Add enforcement after first line of function
    next_line = content.find("\n", func_body_start) + 1
    enforcement_code = '\n    # Plan enforcement\n    user_email = getattr(request_body, "user_email", None) or getattr(request_body, "email", None)\n    if user_email:\n        try:\n            enforce_agent_limit(user_email)\n        except Exception as e:\n            from fastapi import HTTPException\n            if hasattr(e, "status_code"):\n                raise\n'
    content = content[:next_line] + enforcement_code + content[next_line:]
    print("Agent creation enforcement added")
else:
    print("Could not find agent creation endpoint - manual fix needed")

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)

# Also wire into clones
with open("agents/meta_agent/clones.py", encoding="utf-8") as f:
    clones = f.read()

if "plan_enforcement" not in clones:
    clones = clones.replace(
        "from typing import Optional",
        "from typing import Optional\nfrom agents.meta_agent.plan_enforcement import enforce_clone_limit"
    )
    clones = clones.replace(
        'if len(user_clones) >= 10:',
        'enforce_clone_limit(req.user_email)\n    if len(user_clones) >= 10:'
    )
    with open("agents/meta_agent/clones.py", "w", encoding="utf-8") as f:
        f.write(clones)
    print("Clone enforcement added")

python_test = "from agents.meta_agent.api import app; print('OK')"
