with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

if "workflows" not in content:
    content = content.replace(
        "from agents.meta_agent.clones import router as clones_router",
        "from agents.meta_agent.clones import router as clones_router\nfrom agents.meta_agent.workflows import router as workflows_router"
    )
    content = content.replace(
        "app.include_router(clones_router)",
        "app.include_router(clones_router)\napp.include_router(workflows_router)"
    )
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Workflows router registered")
else:
    print("Already registered")
