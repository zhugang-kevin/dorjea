with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "user_keys" not in content:
    content = content.replace(
        "from agents.meta_agent.plan_enforcement import enforce_agent_limit, enforce_clone_limit, check_feature_access",
        "from agents.meta_agent.plan_enforcement import enforce_agent_limit, enforce_clone_limit, check_feature_access\nfrom agents.meta_agent.user_keys import router as userkeys_router"
    )
    content = content.replace(
        "app.include_router(workflows_router)",
        "app.include_router(workflows_router)\napp.include_router(userkeys_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("User keys router registered")
else:
    print("Already registered")
