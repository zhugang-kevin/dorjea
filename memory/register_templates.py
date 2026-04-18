with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "templates_router" not in content:
    content = content.replace(
        "from agents.meta_agent.notifications import router as notifications_router",
        "from agents.meta_agent.notifications import router as notifications_router\nfrom agents.meta_agent.templates import router as templates_router"
    )
    content = content.replace(
        "app.include_router(notifications_router)",
        "app.include_router(notifications_router)\napp.include_router(templates_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Templates router registered")
else:
    print("Already registered")
