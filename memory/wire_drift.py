with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from self_token.budget_manager import get_daily_usage, is_within_daily_budget"
new = """from self_token.budget_manager import get_daily_usage, is_within_daily_budget
from self_monitoring.drift_detector import get_drift_status"""

content = content.replace(old, new)

old_health = '''@app.get("/health")
def health_check() -> dict:
    dashboard = get_factory_dashboard()
    daily_tokens = get_daily_usage()
    return {
        "status": dashboard["status"],
        "service": "Dorjea AI Factory",
        "system": dashboard["system"],
        "alerts": dashboard["alerts"],
        "daily_tokens_used": daily_tokens,
        "daily_budget_ok": is_within_daily_budget(),
    }'''

new_health = '''@app.get("/health")
def health_check() -> dict:
    dashboard = get_factory_dashboard()
    daily_tokens = get_daily_usage()
    drift = get_drift_status()
    all_alerts = dashboard["alerts"] + drift["alerts"]
    overall_status = "alert" if all_alerts else "healthy"
    return {
        "status": overall_status,
        "service": "Dorjea AI Factory",
        "system": dashboard["system"],
        "alerts": all_alerts,
        "daily_tokens_used": daily_tokens,
        "daily_budget_ok": is_within_daily_budget(),
        "drift": {
            "health_score": drift["health_score"],
            "drift_detected": drift["drift_detected"],
            "status": drift["status"],
        },
    }'''

content = content.replace(old_health, new_health)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with drift detection")
