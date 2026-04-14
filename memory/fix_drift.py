with open("self_monitoring/drift_detector.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """def load_recent_audit(hours=24):
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
    return records"""

new = """NOISE_ACTIONS = [
    "TASK_INTAKE_STARTED", "TASK_PLANNING_STARTED",
    "TASK_COMPLETION_FAILED", "TASK_VALIDATION_FAILED",
    "LIFECYCLE_TRANSITION", "MEMORY_WRITE_APPROVED",
    "VERSION_CHECK_COMPLETE", "GATEWAY_ADMITTED",
    "PLAN_CREATED", "PROVIDER_SUCCESS",
]

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
                action = record.get("action", "")
                if ts >= cutoff.isoformat() and action not in NOISE_ACTIONS:
                    records.append(record)
    except Exception:
        pass
    return records"""

content = content.replace(old, new)

with open("self_monitoring/drift_detector.py", "w", encoding="utf-8") as f:
    f.write(content)
print("drift_detector.py fixed")
