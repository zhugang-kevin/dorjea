with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from self_monitoring.drift_detector import get_drift_status"
new = "from self_monitoring.drift_detector import get_drift_status\nfrom agents.meta_agent.version_checker import check_all_versions"

content = content.replace(old, new)

content += """

@app.get("/system/versions")
def get_versions() -> dict:
    return check_all_versions()
"""

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with version endpoint")
