with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "admin_router" not in content:
    content = content.replace(
        "from agents.meta_agent.billing import router as billing_router",
        "from agents.meta_agent.billing import router as billing_router\nfrom agents.meta_agent.admin import router as admin_router"
    )
    content = content.replace(
        "app.include_router(billing_router)",
        "app.include_router(billing_router)\napp.include_router(admin_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Admin router registered")
else:
    print("Already registered")
