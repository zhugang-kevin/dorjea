import uuid
from datetime import datetime
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from self_defence.injection_detector import is_safe
from self_defence.rate_limiter import rate_limiter
from self_token.budget_manager import is_within_daily_budget
from self_governance.policy_engine import policy_engine


class TaskEntryGateway:
    def __init__(self):
        self.task_chain_counter = {}
        self.MAX_TASK_CHAIN = 10
        self.MAX_RECURSION_DEPTH = 3

    def _log(self, task_id, action, details, success=True):
        write_audit_entry(AuditEntry(
            agent_id="gateway",
            task_id=task_id,
            action=action,
            details=details,
            success=success,
        ))

    def validate_and_admit(self, request, source="founder", parent_task_id=None):
        task_id = str(uuid.uuid4())
        errors = []

        if not request or len(request.strip()) < 5:
            return None, ["Request is too short or empty"]

        safe, reason = is_safe(request, agent_id="gateway")
        if not safe:
            self._log(task_id, "GATEWAY_BLOCKED_INJECTION",
                     {"reason": reason}, success=False)
            return None, ["Security filter blocked request: " + reason]

        if not rate_limiter.wait_if_needed("gateway", timeout=3.0):
            self._log(task_id, "GATEWAY_BLOCKED_RATE_LIMIT",
                     {}, success=False)
            return None, ["Rate limit exceeded. Please wait."]

        if not is_within_daily_budget():
            self._log(task_id, "GATEWAY_BLOCKED_BUDGET",
                     {}, success=False)
            return None, ["Daily token budget exceeded."]

        if parent_task_id:
            depth = self.task_chain_counter.get(parent_task_id, 0) + 1
            if depth > self.MAX_RECURSION_DEPTH:
                self._log(task_id, "GATEWAY_BLOCKED_RECURSION",
                         {"depth": depth}, success=False)
                return None, ["Maximum recursion depth exceeded: " + str(depth)]
            self.task_chain_counter[task_id] = depth

        task_envelope = {
            "task_id": task_id,
            "request": request.strip(),
            "source": source,
            "parent_task_id": parent_task_id,
            "submitted_at": datetime.utcnow().isoformat(),
            "status": "admitted",
        }

        self._log(task_id, "GATEWAY_ADMITTED",
                 {"source": source, "request_preview": request[:100]})
        return task_envelope, []


gateway = TaskEntryGateway()