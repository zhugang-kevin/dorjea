with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

# Check what routers are already imported
imports_needed = {
    "analytics_router": "from agents.meta_agent.analytics import router as analytics_router",
    "support_router": "from agents.meta_agent.support import router as support_router",
    "clones_router": "from agents.meta_agent.clones import router as clones_router",
    "workflows_router": "from agents.meta_agent.workflows import router as workflows_router",
    "apikeys_router": "from agents.meta_agent.api_keys import router as apikeys_router",
    "userkeys_router": "from agents.meta_agent.user_keys import router as userkeys_router",
    "billing_router": "from agents.meta_agent.billing import router as billing_router",
    "admin_router": "from agents.meta_agent.admin import router as admin_router",
    "notifications_router": "from agents.meta_agent.notifications import router as notifications_router",
}

includes_needed = {
    "analytics_router": "app.include_router(analytics_router)",
    "support_router": "app.include_router(support_router)",
    "clones_router": "app.include_router(clones_router)",
    "workflows_router": "app.include_router(workflows_router)",
    "apikeys_router": "app.include_router(apikeys_router)",
    "userkeys_router": "app.include_router(userkeys_router)",
    "billing_router": "app.include_router(billing_router)",
    "admin_router": "app.include_router(admin_router)",
    "notifications_router": "app.include_router(notifications_router)",
}

for key, imp in imports_needed.items():
    if key not in content:
        content = content.replace(
            "from agents.meta_agent.affiliate import router as affiliate_router",
            "from agents.meta_agent.affiliate import router as affiliate_router\n" + imp
        )
        print(f"Added import: {key}")

for key, inc in includes_needed.items():
    if inc not in content:
        content = content.replace(
            "app.include_router(affiliate_router)",
            "app.include_router(affiliate_router)\n" + inc
        )
        print(f"Added include: {key}")

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
