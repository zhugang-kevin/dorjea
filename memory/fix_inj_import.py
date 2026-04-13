with open("self_defence/injection_detector.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "from tools.audit_logger import log_action",
    "from agents.meta_agent.audit_logger import write_audit_entry\nfrom agents.meta_agent.models import AuditEntry\n\ndef log_action(agent_id, action, details, success=True):\n    write_audit_entry(AuditEntry(agent_id=agent_id, task_id='system', action=action, details=details, success=success))"
)

with open("self_defence/injection_detector.py", "w", encoding="utf-8") as f:
    f.write(content)
print("import fixed")
