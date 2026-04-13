import json
from datetime import datetime
from pathlib import Path
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

TASK_LOG = Path("logs/task_integrity.jsonl")


def validate_task_structure(task):
    errors = []
    if not task.get("task_id"):
        errors.append("Missing task_id")
    if not task.get("request") or len(task.get("request", "").strip()) < 5:
        errors.append("Missing or too short request")
    if not task.get("source"):
        errors.append("Missing source")
    if not task.get("submitted_at"):
        errors.append("Missing submitted_at timestamp")
    return len(errors) == 0, errors


def record_task_lifecycle(task_id, stage, status, details=None):
    record = {
        "task_id": task_id,
        "stage": stage,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {},
    }
    TASK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TASK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + chr(10))

    write_audit_entry(AuditEntry(
        agent_id="task_integrity_loop",
        task_id=task_id,
        action="TASK_" + stage.upper() + "_" + status.upper(),
        details=details or {},
        success=(status == "passed"),
    ))


def run_task_integrity_check(task):
    task_id = task.get("task_id", "unknown")
    record_task_lifecycle(task_id, "intake", "started")

    valid, errors = validate_task_structure(task)
    if not valid:
        record_task_lifecycle(task_id, "validation", "failed",
                             {"errors": errors})
        return False, errors

    record_task_lifecycle(task_id, "validation", "passed")
    record_task_lifecycle(task_id, "planning", "started")
    return True, []


def complete_task_record(task_id, status, tokens_used=0, output_preview=""):
    record_task_lifecycle(task_id, "completion", status, {
        "tokens_used": tokens_used,
        "output_preview": output_preview[:100],
    })


def get_task_history(task_id):
    if not TASK_LOG.exists():
        return []
    records = []
    try:
        with open(TASK_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("task_id") == task_id:
                    records.append(r)
    except Exception:
        pass
    return records