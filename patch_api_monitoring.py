PATH = r"E:\Dorjea\Dorjea\agents\meta_agent\api.py"

with open(PATH, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    "from agents.meta_agent.auth_extended import router as auth_extended_router",
    "from agents.meta_agent.auth_extended import router as auth_extended_router\n"
    "from agents.meta_agent.monitoring import router as monitoring_router",
    1,
)

c = c.replace(
    "app.include_router(auth_extended_router)",
    "app.include_router(auth_extended_router)\n"
    "app.include_router(monitoring_router)",
    1,
)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(c)

assert "monitoring_router" in c
print("api.py patched OK")
