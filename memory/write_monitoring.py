content = """
import os
import json
import psutil
from datetime import datetime
from pathlib import Path

METRICS_PATH = Path(os.getenv("METRICS_LOG_PATH", "logs/metrics.jsonl"))


def collect_system_health():
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "memory_available_mb": round(psutil.virtual_memory().available / 1024 / 1024, 1),
        "disk_percent": psutil.disk_usage("/").percent,
        "disk_free_gb": round(psutil.disk_usage("/").free / 1024 / 1024 / 1024, 2),
    }


def get_recent_metrics(n=20):
    if not METRICS_PATH.exists():
        return []
    try:
        with open(METRICS_PATH, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        recent = lines[-n:]
        return [json.loads(l) for l in recent]
    except Exception:
        return []


def check_health_alerts(health):
    alerts = []
    if health["cpu_percent"] > 90:
        alerts.append("HIGH CPU: " + str(health["cpu_percent"]) + "%")
    if health["memory_percent"] > 85:
        alerts.append("HIGH MEMORY: " + str(health["memory_percent"]) + "%")
    if health["disk_percent"] > 90:
        alerts.append("HIGH DISK: " + str(health["disk_percent"]) + "%")
    return alerts


def get_factory_dashboard():
    health = collect_system_health()
    alerts = check_health_alerts(health)
    recent = get_recent_metrics(10)
    total_tokens_today = sum(m.get("total_tokens", 0) for m in recent)
    return {
        "status": "alert" if alerts else "healthy",
        "system": health,
        "alerts": alerts,
        "recent_token_usage": total_tokens_today,
        "recent_calls": len(recent),
    }
"""

with open("self_monitoring/health_monitor.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("health_monitor.py created")
