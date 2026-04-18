with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

new_imports = """
from agents.meta_agent.analytics import router as analytics_router
from agents.meta_agent.support import router as support_router
from agents.meta_agent.clones import router as clones_router
from agents.meta_agent.workflows import router as workflows_router
from agents.meta_agent.api_keys import router as apikeys_router
from agents.meta_agent.user_keys import router as userkeys_router
from agents.meta_agent.billing import router as billing_router
from agents.meta_agent.admin import router as admin_router
from agents.meta_agent.notifications import router as notifications_router
from agents.meta_agent.notifications import send_welcome_email, send_agent_created_email
from agents.meta_agent.plan_enforcement import enforce_agent_limit, enforce_clone_limit
"""

new_includes = """
app.include_router(analytics_router)
app.include_router(support_router)
app.include_router(clones_router)
app.include_router(workflows_router)
app.include_router(apikeys_router)
app.include_router(userkeys_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(notifications_router)
"""

# Add imports after the affiliate import
old_import = "from agents.meta_agent.affiliate import create_affiliate, get_affiliate_stats, record_referral\nfrom agents.meta_agent.affiliate import create_affiliate, get_affiliate_stats, record_referral"
new_import = "from agents.meta_agent.affiliate import create_affiliate, get_affiliate_stats, record_referral" + new_imports

content = content.replace(old_import, new_import)

# Add includes after app = FastAPI(...) block — find the CORS middleware section
old_cors = 'app.add_middleware(\n    CORSMiddleware,'
new_cors = new_includes + '\napp.add_middleware(\n    CORSMiddleware,'

content = content.replace(old_cors, new_cors)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
