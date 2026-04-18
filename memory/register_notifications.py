with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "notifications_router" not in content:
    content = content.replace(
        "from agents.meta_agent.admin import router as admin_router",
        "from agents.meta_agent.admin import router as admin_router\nfrom agents.meta_agent.notifications import router as notifications_router\nfrom agents.meta_agent.notifications import send_welcome_email, send_agent_created_email"
    )
    content = content.replace(
        "app.include_router(admin_router)",
        "app.include_router(admin_router)\napp.include_router(notifications_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Notifications router registered")
else:
    print("Already registered")
