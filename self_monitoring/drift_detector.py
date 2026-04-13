import json
from datetime import datetime, timedelta
from pathlib import Path

METRICS_PATH = Path("logs/metrics.jsonl")
DRIFT_LOG_PATH = Path("logs/drift_alerts.jsonl")

THRESHOLDS = {
    "error_rate_max": 0.3,
    "min_success_rate": 0.7,
    "max_avg_tokens": 18000,
    "max_avg_latency_seconds": 90,
}


def load_recent_metrics(hours=24):
    if not METRICS_PATH.exists():
        return []
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    records = []
    try:
        with open(METRICS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                ts = record.get("timestamp", "")
                if ts >= cutoff.isoformat():
                    records.append(record)
    except Exception:
        pass
    return records


def load_recent_audit(hours=24):
    audit_path = Path("logs/audit.jsonl")
    if not audit_path.exists():
        return []
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    records = []
    try:
        with open(audit_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                ts = record.get("logged_at", "")
                if ts >= cutoff.isoformat():
                    records.append(record)
    except Exception:
        pass
    return records


def calculate_system_health_score(hours=24):
    audit_records = load_recent_audit(hours)
    if not audit_records:
        return 1.0, []

    total = len(audit_records)
    failed = sum(1 for r in audit_records if not r.get("success", True))
    error_rate = failed / total if total > 0 else 0
    success_rate = 1 - error_rate

    metrics = load_recent_metrics(hours)
    avg_tokens = 0
    if metrics:
        avg_tokens = sum(m.get("total_tokens", 0) for m in metrics) / len(metrics)

    alerts = []
    if error_rate > THRESHOLDS["error_rate_max"]:
        alerts.append("HIGH ERROR RATE: " + str(round(error_rate * 100, 1)) + "%")
    if success_rate < THRESHOLDS["min_success_rate"]:
        alerts.append("LOW SUCCESS RATE: " + str(round(success_rate * 100, 1)) + "%")
    if avg_tokens > THRESHOLDS["max_avg_tokens"]:
        alerts.append("HIGH AVG TOKENS: " + str(int(avg_tokens)))

    health_score = max(0.0, success_rate - (error_rate * 0.5))
    return round(health_score, 3), alerts


def run_drift_detection():
    health_score, alerts = calculate_system_health_score()
    drift_detected = len(alerts) > 0

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "health_score": health_score,
        "drift_detected": drift_detected,
        "alerts": alerts,
        "status": "ALERT" if drift_detected else "HEALTHY",
    }

    DRIFT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DRIFT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + chr(10))

    return result


def get_drift_status():
    return run_drift_detection()