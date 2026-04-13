import json
from datetime import datetime
from pathlib import Path
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry


MEMORY_DIR = Path("memory/agent_memory")
MIN_CONFIDENCE = 0.7


def validate_memory_write(agent_name, key, value, confidence=1.0):
    errors = []
    if not agent_name or not agent_name.strip():
        errors.append("agent_name is required")
    if not key or not key.strip():
        errors.append("memory key is required")
    if value is None:
        errors.append("memory value cannot be None")
    if confidence < MIN_CONFIDENCE:
        errors.append(
            "confidence " + str(confidence) +
            " is below minimum threshold " + str(MIN_CONFIDENCE)
        )
    if isinstance(value, str) and len(value) > 50000:
        errors.append("memory value exceeds maximum size limit")
    return len(errors) == 0, errors


def write_agent_memory(agent_name, key, value, confidence=1.0):
    valid, errors = validate_memory_write(agent_name, key, value, confidence)
    if not valid:
        write_audit_entry(AuditEntry(
            agent_id=agent_name,
            task_id="memory",
            action="MEMORY_WRITE_REJECTED",
            details={"key": key, "errors": errors},
            success=False,
        ))
        return False, errors

    agent_dir = MEMORY_DIR / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
    memory_path = agent_dir / (safe_key + ".json")

    record = {
        "agent_name": agent_name,
        "key": key,
        "value": value,
        "confidence": confidence,
        "written_at": datetime.utcnow().isoformat(),
    }

    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    write_audit_entry(AuditEntry(
        agent_id=agent_name,
        task_id="memory",
        action="MEMORY_WRITE_APPROVED",
        details={"key": key, "confidence": confidence},
        success=True,
    ))
    return True, []


def read_agent_memory(agent_name, key):
    safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
    memory_path = MEMORY_DIR / agent_name / (safe_key + ".json")
    if not memory_path.exists():
        return None
    with open(memory_path, "r", encoding="utf-8") as f:
        record = json.load(f)
    return record.get("value")


def list_agent_memory(agent_name):
    agent_dir = MEMORY_DIR / agent_name
    if not agent_dir.exists():
        return []
    return [f.stem for f in agent_dir.glob("*.json")]