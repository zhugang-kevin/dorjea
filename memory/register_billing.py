with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "billing" not in content or "billing_router" not in content:
    content = content.replace(
        "from agents.meta_agent.user_keys import router as userkeys_router",
        "from agents.meta_agent.user_keys import router as userkeys_router\nfrom agents.meta_agent.billing import router as billing_router"
    )
    content = content.replace(
        "app.include_router(userkeys_router)",
        "app.include_router(userkeys_router)\napp.include_router(billing_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Billing router registered")
else:
    print("Already registered")
