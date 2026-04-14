content = """
import json
import uuid
from datetime import datetime
from pathlib import Path
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

MESSAGE_LOG = Path("logs/agent_messages.jsonl")

VALID_TASK_TYPES = [
    "research", "analysis", "content_creation", "code_generation",
    "verification", "planning", "reporting", "data_processing",
    "review", "escalation", "notification",
]


def create_message(sender_agent, receiver_agent, task_type, payload, task_id=None):
    if task_type not in VALID_TASK_TYPES:
        return None, "Invalid task type: " + task_type + ". Allowed: " + str(VALID_TASK_TYPES)
    message = {
        "message_id": str(uuid.uuid4()),
        "task_id": task_id or str(uuid.uuid4()),
        "sender_agent": sender_agent,
        "receiver_agent": receiver_agent,
        "task_type": task_type,
        "payload": payload,
        "status": "pending",
        "timestamp": datetime.utcnow().isoformat(),
        "schema_version": "1.0",
    }
    return message, None


def send_message(sender_agent, receiver_agent, task_type, payload, task_id=None):
    message, error = create_message(sender_agent, receiver_agent, task_type, payload, task_id)
    if error:
        return None, error
    MESSAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(MESSAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(message) + chr(10))
    write_audit_entry(AuditEntry(
        agent_id=sender_agent,
        task_id=message["task_id"],
        action="MESSAGE_SENT",
        details={"receiver": receiver_agent, "task_type": task_type, "payload_preview": str(payload)[:100]},
        success=True,
    ))
    return message, None


def get_messages(agent_name, role="receiver", status=None):
    if not MESSAGE_LOG.exists():
        return []
    messages = []
    try:
        with open(MESSAGE_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if role == "receiver" and msg.get("receiver_agent") == agent_name:
                    if status is None or msg.get("status") == status:
                        messages.append(msg)
                elif role == "sender" and msg.get("sender_agent") == agent_name:
                    if status is None or msg.get("status") == status:
                        messages.append(msg)
    except Exception:
        pass
    return messages


def validate_message(message):
    required = ["message_id", "task_id", "sender_agent", "receiver_agent", "task_type", "payload", "status", "timestamp"]
    errors = []
    for field in required:
        if field not in message:
            errors.append("Missing field: " + field)
    if message.get("task_type") not in VALID_TASK_TYPES:
        errors.append("Invalid task_type: " + str(message.get("task_type")))
    return len(errors) == 0, errors
"""

with open("agents/meta_agent/communication_protocol.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("communication_protocol.py created")
