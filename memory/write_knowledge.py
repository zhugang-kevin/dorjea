content = """
import json
import hashlib
from datetime import datetime
from pathlib import Path
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

KNOWLEDGE_LOG = Path("logs/knowledge_consistency.jsonl")
KNOWLEDGE_STORE = Path("memory/knowledge_store.jsonl")


def _hash_content(content):
    return hashlib.sha256(str(content).encode()).hexdigest()[:16]


def store_knowledge(agent_id, key, content, source="agent", confidence=1.0):
    existing = get_knowledge(key)
    if existing:
        if existing.get("content_hash") == _hash_content(content):
            return True, "Knowledge already exists and is identical"
        conflict = {
            "timestamp": datetime.utcnow().isoformat(),
            "key": key,
            "type": "conflict",
            "existing_source": existing.get("source"),
            "new_source": source,
            "resolution": "new_version_stored",
        }
        KNOWLEDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(KNOWLEDGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(conflict) + chr(10))
        write_audit_entry(AuditEntry(
            agent_id=agent_id,
            task_id="knowledge",
            action="KNOWLEDGE_CONFLICT_RESOLVED",
            details={"key": key, "resolution": "new_version_stored"},
            success=True,
        ))

    record = {
        "key": key,
        "content": content,
        "content_hash": _hash_content(content),
        "agent_id": agent_id,
        "source": source,
        "confidence": confidence,
        "version": (existing.get("version", 0) + 1) if existing else 1,
        "stored_at": datetime.utcnow().isoformat(),
    }
    KNOWLEDGE_STORE.parent.mkdir(parents=True, exist_ok=True)
    existing_records = _load_all_records()
    existing_records[key] = record
    with open(KNOWLEDGE_STORE, "w", encoding="utf-8") as f:
        for r in existing_records.values():
            f.write(json.dumps(r) + chr(10))
    return True, "Knowledge stored successfully"


def get_knowledge(key):
    records = _load_all_records()
    return records.get(key)


def _load_all_records():
    if not KNOWLEDGE_STORE.exists():
        return {}
    records = {}
    try:
        with open(KNOWLEDGE_STORE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    records[r["key"]] = r
    except Exception:
        pass
    return records


def check_consistency():
    records = _load_all_records()
    issues = []
    keys_seen = {}
    for key, record in records.items():
        if key in keys_seen:
            issues.append("Duplicate key detected: " + key)
        keys_seen[key] = True
        if record.get("confidence", 1.0) < 0.5:
            issues.append("Low confidence knowledge: " + key)
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_records": len(records),
        "issues_found": len(issues),
        "issues": issues,
        "status": "CONSISTENT" if not issues else "INCONSISTENT",
    }


def get_knowledge_summary():
    records = _load_all_records()
    return {
        "total_records": len(records),
        "keys": list(records.keys())[:20],
        "consistency": check_consistency(),
    }
"""

with open("agents/meta_agent/knowledge_consistency.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("knowledge_consistency.py created")
