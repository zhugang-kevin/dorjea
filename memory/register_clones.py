with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "clones" not in content:
    content = content.replace(
        "from agents.meta_agent.support import router as support_router",
        "from agents.meta_agent.support import router as support_router\nfrom agents.meta_agent.clones import router as clones_router"
    )
    content = content.replace(
        "app.include_router(support_router)",
        "app.include_router(support_router)\napp.include_router(clones_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Clones router registered")
else:
    print("Already registered")
