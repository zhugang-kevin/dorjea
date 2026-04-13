with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from self_monitoring.drift_detector import get_drift_status"
new = "from self_monitoring.drift_detector import get_drift_status\nfrom self_monitoring.agent_performance import get_performance_summary"
content = content.replace(old, new)

addition = """

@app.get("/performance")
def get_performance() -> dict:
    return get_performance_summary()"""

content = content + addition

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with performance endpoint")
