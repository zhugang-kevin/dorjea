"""
audit_logger.py — Writes audit entries to logs/audit.jsonl.
Every node calls write_audit_entry() after executing.
The log is append-only. Never delete or modify existing entries.
"""
from __future__ import annotations
import os
from pathlib import Path
from agents.meta_agent.models import AuditEntry

LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "logs/audit.jsonl"))


def write_audit_entry(entry: AuditEntry) -> None:
    """
    Append a single AuditEntry to the audit log as one JSON line.
    Creates the log file and parent directory if they do not exist.
    Never raises — logs the error to stderr if write fails.
    """
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
    except Exception as e:
        import sys
        print(f"AUDIT LOG ERROR: {e}", file=sys.stderr)


def read_last_entry() -> AuditEntry | None:
    """
    Read the most recent entry from the audit log.
    Returns None if the log is empty or does not exist.
    """
    if not LOG_PATH.exists():
        return None
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return None
        return AuditEntry.model_validate_json(lines[-1])
    except Exception:
        return None


def read_all_entries(limit: int = 50) -> list[AuditEntry]:
    """
    Read the last N entries from the audit log.
    Returns empty list if log does not exist or is empty.
    """
    if not LOG_PATH.exists():
        return []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        recent = lines[-limit:]
        return [AuditEntry.model_validate_json(line) for line in recent]
    except Exception:
        return []
