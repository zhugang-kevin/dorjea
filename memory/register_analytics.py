with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "analytics" not in content:
    content = content.replace(
        "from agents.meta_agent.api_keys import router as apikeys_router",
        "from agents.meta_agent.api_keys import router as apikeys_router\nfrom agents.meta_agent.analytics import router as analytics_router"
    )
    content = content.replace(
        "app.include_router(apikeys_router)",
        "app.include_router(apikeys_router)\napp.include_router(analytics_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Analytics router registered")
else:
    print("Already registered")
