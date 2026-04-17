with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "support" not in content:
    content = content.replace(
        "from agents.meta_agent.analytics import router as analytics_router",
        "from agents.meta_agent.analytics import router as analytics_router\nfrom agents.meta_agent.support import router as support_router"
    )
    content = content.replace(
        "app.include_router(analytics_router)",
        "app.include_router(analytics_router)\napp.include_router(support_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Support router registered")
else:
    print("Already registered")
