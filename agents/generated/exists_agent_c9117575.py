"""
exists_agent_c9117575.py

Production agent for the general department.
Handles task parsing, file/registry management, workflow execution,
decision rule application, output validation, audit logging, and reporting.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
import anthropic


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TaskSpec(BaseModel):
    """Validated representation of an incoming task specification."""

    task_id: str = Field(..., description="Unique identifier for the task")
    description: str = Field(..., description="Human-readable task description")
    department: str = Field(default="general", description="Owning department")
    priority: str = Field(default="normal", description="Task priority level")
    payload: dict = Field(default_factory=dict, description="Arbitrary task payload")


class AuditEntry(BaseModel):
    """Single audit log entry for a state-changing operation."""

    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")
    agent: str = Field(..., description="Agent name that produced this entry")
    operation: str = Field(..., description="Name of the operation performed")
    status: str = Field(..., description="'success' or 'failure'")
    detail: str = Field(default="", description="Additional context or error message")


class CompletionReport(BaseModel):
    """Structured completion report emitted at the end of a run."""

    task_id: str
    agent: str
    department: str
    started_at: str
    completed_at: str
    status: str
    summary: str
    audit_log: list[AuditEntry]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ExistsAgentC9117575:
    """
    Production AI agent for the general department.

    Responsibilities
    ----------------
    - Parse and validate incoming task specifications.
    - Retrieve and manage files and records via filesystem_server and registry_server.
    - Execute assigned workflows in strict accordance with the execution_workflow sequence.
    - Apply decision_rules consistently at every action point.
    - Produce structured, validated outputs that meet quality_standards benchmarks.
    - Generate and persist audit logs for all state-changing operations.
    - Emit completion reports and escalation notices via the defined communication_protocol.
    - Maintain operational scope strictly within the general department boundaries.
    """

    AGENT_NAME: str = "exists_agent_c9117575"
    DEPARTMENT: str = "general"
    MODEL: str = "claude-sonnet-4-6"

    # Allowed MCP-style tool names
    ALLOWED_TOOLS: list[str] = ["filesystem_server", "registry_server"]

    def __init__(self) -> None:
        """
        Initialise the agent by reading all configuration from environment variables.

        Environment variables
        ---------------------
        ANTHROPIC_API_KEY       : Required. Anthropic API key.
        AGENT_MAX_TOKENS        : Optional. Max tokens for model responses (default 4096).
        AGENT_LOG_LEVEL         : Optional. Python logging level name (default INFO).
        AGENT_AUDIT_LOG_PATH    : Optional. File path to persist audit entries (default audit.jsonl).
        AGENT_ESCALATION_EMAIL  : Optional. E-mail address for escalation notices.
        """
        self._api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")

        self._max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        self._audit_log_path: str = os.getenv("AGENT_AUDIT_LOG_PATH", "audit.jsonl")
        self._escalation_email: str = os.getenv("AGENT_ESCALATION_EMAIL", "")

        log_level_name: str = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
        log_level: int = getattr(logging, log_level_name, logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        self._logger: logging.Logger = logging.getLogger(self.AGENT_NAME)

        self._client: anthropic.Anthropic = anthropic.Anthropic(api_key=self._api_key)
        self._audit_entries: list[AuditEntry] = []

        self._logger.info("Agent %s initialised for department '%s'.", self.AGENT_NAME, self.DEPARTMENT)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, task: str) -> str:
        """
        Execute the full agent lifecycle for the given task string.

        Parameters
        ----------
        task : str
            Raw task specification (JSON string or plain description).

        Returns
        -------
        str
            JSON-serialised CompletionReport.
        """
        started_at: str = _utc_now()
        self._audit_entries.clear()

        self._logger.info("Starting task execution.")

        # 1. Parse and validate the incoming task specification
        task_spec: Optional[TaskSpec] = self._parse_task(task)
        if task_spec is None:
            # Fallback: treat the raw string as a description
            task_spec = TaskSpec(
                task_id=f"auto-{_utc_now()}",
                description=task,
                department=self.DEPARTMENT,
            )
            self._record_audit("parse_task", "success", "Fallback task spec created from raw string.")
        else:
            self._record_audit("parse_task", "success", f"Task spec validated: {task_spec.task_id}")

        # 2. Enforce department boundary
        if task_spec.department != self.DEPARTMENT:
            detail = (
                f"Task department '{task_spec.department}' is outside the allowed "
                f"scope '{self.DEPARTMENT}'."
            )
            self._record_audit("department_check", "failure", detail)
            self._logger.warning(detail)
            return self._build_report(task_spec, started_at, "escalated", detail)

        self._record_audit("department_check", "success", "Department boundary verified.")

        # 3. Execute the agentic workflow via the Anthropic model
        workflow_result: str = await self._execute_workflow(task_spec)

        # 4. Persist audit log
        self._persist_audit_log()

        # 5. Build and return the completion report
        return self._build_report(task_spec, started_at, "completed", workflow_result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_task(self, raw: str) -> Optional[TaskSpec]:
        """
        Attempt to parse *raw* as a JSON object and validate it as a TaskSpec.

        Parameters
        ----------
        raw : str
            Raw input string, potentially JSON.

        Returns
        -------
        TaskSpec or None
            Validated spec, or None if parsing/validation fails.
        """
        try:
            data: dict = json.loads(raw)
            spec = TaskSpec(**data)
            return spec
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            self._logger.debug("Task spec parse attempt failed: %s", exc)
            return None

    async def _execute_workflow(self, task_spec: TaskSpec) -> str:
        """
        Drive the Anthropic model through the execution_workflow sequence.

        The model is given a system prompt that encodes the agent's responsibilities,
        decision_rules, and quality_standards. Tool definitions for filesystem_server
        and registry_server are declared so the model can request their use; this
        agent intercepts those requests and executes them locally.

        Parameters
        ----------
        task_spec : TaskSpec
            Validated task specification.

        Returns
        -------
        str
            Final textual summary produced by the model.
        """
        system_prompt: str = self._build_system_prompt()
        user_message: str = self._build_user_message(task_spec)

        tools = self._tool_definitions()
        messages: list[dict] = [{"role": "user", "content": user_message}]

        final_text: str = ""
        iteration: int = 0
        max_iterations: int = 10  # guard against infinite loops

        while iteration < max_iterations:
            iteration += 1
            self._logger.debug("Workflow iteration %d.", iteration)

            try:
                response = self._client.messages.create(
                    model=self.MODEL,
                    max_tokens=self._max_tokens,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
                self._record_audit(
                    "model_call",
                    "success",
                    f"Iteration {iteration}, stop_reason={response.stop_reason}",
                )
            except anthropic.APIError as exc:
                self._record_audit("model_call", "failure", str(exc))
                self._logger.error("Anthropic API error: %s", exc)
                raise

            # Collect text blocks and tool-use blocks
            text_parts: list[str] = []
            tool_uses: list[dict] = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(
                        {"id": block.id, "name": block.name, "input": block.input}
                    )

            if text_parts:
                final_text = " ".join(text_parts)

            if response.stop_reason == "end_turn" or not tool_uses:
                break

            # Process tool calls and feed results back
            messages.append({"role": "assistant", "content": response.content})
            tool_results: list[dict] = []

            for tool_use in tool_uses:
                result_content: str = self._dispatch_tool(
                    tool_use["name"], tool_use["input"]
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use["id"],
                        "content": result_content,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        if iteration >= max_iterations:
            self._record_audit(
                "workflow_guard",
                "failure",
                f"Reached max iterations ({max_iterations}). Workflow terminated.",
            )
            self._logger.warning("Max workflow iterations reached.")

        return final_text or "Workflow completed with no textual output."

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Route a model-requested tool call to the appropriate handler.

        Parameters
        ----------
        tool_name : str
            Name of the tool as declared in the tool definitions.
        tool_input : dict
            Arguments provided by the model.

        Returns
        -------
        str
            JSON string result to return to the model.
        """
        if tool_name not in self.ALLOWED_TOOLS:
            msg = f"Tool '{tool_name}' is not in the allowed tool list."
            self._record_audit("tool_dispatch", "failure", msg)
            return json.dumps({"error": msg})

        if tool_name == "filesystem_server":
            return self._handle_filesystem_server(tool_input)
        if tool_name == "registry_server":
            return self._handle_registry_server(tool_input)

        return json.dumps({"error": f"No handler implemented for tool '{tool_name}'."})

    def _handle_filesystem_server(self, params: dict) -> str:
        """
        Execute a filesystem_server operation.

        Supported operations: read_file, write_file, list_directory, delete_file.

        Parameters
        ----------
        params : dict
            Must contain 'operation' and relevant path/content keys.

        Returns
        -------
        str
            JSON-encoded result or error.
        """
        operation: str = params.get("operation", "")
        path: str = params.get("path", "")

        try:
            if operation == "read_file":
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                self._record_audit("filesystem_server.read_file", "success", path)
                return json.dumps({"content": content})

            if operation == "write_file":
                content: str = params.get("content", "")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                self._record_audit("filesystem_server.write_file", "success", path)
                return json.dumps({"written": len(content), "path": path})

            if operation == "list_directory":
                entries = os.listdir(path)
                self._record_audit("filesystem_server.list_directory", "success", path)
                return json.dumps({"entries": entries})

            if operation == "delete_file":
                os.remove(path)
                self._record_audit("filesystem_server.delete_file", "success", path)
                return json.dumps({"deleted": path})

            msg = f"Unknown filesystem operation: '{operation}'."
            self._record_audit("filesystem_server", "failure", msg)
            return json.dumps({"error": msg})

        except OSError as exc:
            detail = f"filesystem_server.{operation} failed for '{path}': {exc}"
            self._record_audit(f"filesystem_server.{operation}", "failure", detail)
            self._logger.error(detail)
            return json.dumps({"error": detail})

    def _handle_registry_server(self, params: dict) -> str:
        """
        Execute a registry_server operation backed by a local JSON file store.

        Supported operations: get_record, set_record, delete_record, list_keys.

        Parameters
        ----------
        params : dict
            Must contain 'operation' and relevant key/value fields.

        Returns
        -------
        str
            JSON-encoded result or error.
        """
        registry_path: str = os.getenv("AGENT_REGISTRY_PATH", "registry.json")
        operation: str = params.get("operation", "")
        key: str = params.get("key", "")

        try:
            # Load existing registry
            registry: dict = {}
            if os.path.exists(registry_path):
                with open(registry_path, "r", encoding="utf-8") as fh:
                    registry = json.load(fh)

            if operation == "get_record":
                value = registry.get(key)
                self._record_audit("registry_server.get_record", "success", key)
                return json.dumps({"key": key, "value": value})

            if operation == "set_record":
                value = params.get("value")
                registry[key] = value
                with open(registry_path, "w", encoding="utf-8") as fh:
                    json.dump(registry, fh, indent=2)
                self._record_audit("registry_server.set_record", "success", key)
                return json.dumps({"key": key, "stored": True})

            if operation == "delete_record":
                existed = key in registry
                registry.pop(key, None)
                with open(registry_path, "w", encoding="utf-8") as fh:
                    json.dump(registry, fh, indent=2)
                self._record_audit("registry_server.delete_record", "success", key)
                return json.dumps({"key": key, "deleted": existed})

            if operation == "list_keys":
                keys = list(registry.keys())
                self._record_audit("registry_server.list_keys", "success", registry_path)
                return json.dumps({"keys": keys})

            msg = f"Unknown registry operation: '{operation}'."
            self._record_audit("registry_server", "failure", msg)
            return json.dumps({"error": msg})

        except (OSError, json.JSONDecodeError) as exc:
            detail = f"registry_server.{operation} failed: {exc}"
            self._record_audit(f"registry_server.{operation}", "failure", detail)
            self._logger.error(detail)
            return json.dumps({"error": detail})

    def _record_audit(self, operation: str, status: str, detail: str = "") -> None:
        """
        Append an AuditEntry to the in-memory audit log.

        Parameters
        ----------
        operation : str
            Name of the operation being audited.
        status : str
            'success' or 'failure'.
        detail : str
            Optional additional context.
        """
        entry = AuditEntry(
            timestamp=_utc_now(),
            agent=self.AGENT_NAME,
            operation=operation,
            status=status,
            detail=detail,
        )
        self._audit_entries.append(entry)
        self._logger.debug("AUDIT [%s] %s: %s", status.upper(), operation, detail)

    def _persist_audit_log(self) -> None:
        """
        Append all current in-memory audit entries to the configured JSONL file.

        Each line in the file is a JSON-serialised AuditEntry.
        """
        try:
            with open(self._audit_log_path, "a", encoding="utf-8") as fh:
                for entry in self._audit_entries:
                    fh.write(entry.model_dump_json() + "\n")
            self._logger.info(
                "Persisted %d audit entries to '%s'.",
                len(self._audit_entries),
                self._audit_log_path,
            )
        except OSError as exc:
            self._logger.error("Failed to persist audit log: %s", exc)

    def _build_report(
        self,
        task_spec: TaskSpec,
        started_at: str,
        status: str,
        summary: str,
    ) -> str:
        """
        Construct and serialise a CompletionReport.

        Parameters
        ----------
        task_spec : TaskSpec
            The validated task specification.
        started_at : str
            ISO-8601 UTC timestamp when the run started.
        status : str
            Final status string, e.g. 'completed', 'escalated', 'failed'.
        summary : str
            Human-readable summary of the outcome.

        Returns
        -------
        str
            JSON-serialised CompletionReport.
        """
        report = CompletionReport(
            task_id=task_spec.task_id,
            agent=self.AGENT_NAME,
            department=self.DEPARTMENT,
            started_at=started_at,
            completed_at=_utc_now(),
            status=status,
            summary=summary,
            audit_log=list(self._audit_entries),
        )

        if status == "escalated" and self._escalation_email:
            self._logger.warning(
                "ESCALATION NOTICE → %s | Task: %s | Reason: %s",
                self._escalation_email,
                task_spec.task_id,
                summary,
            )

        return report.model_dump_json(indent=2)

    def _build_system_prompt(self) -> str:
        """
        Construct the system prompt that encodes the agent's mission, responsibilities,
        decision_rules, and quality_standards.

        Returns
        -------
        str
            Fully formed system prompt string.
        """
        return (
            f"You are {self.AGENT_NAME}, a production AI agent operating within the "
            f"'{self.DEPARTMENT}' department.\n\n"
            "MISSION:\n"
            "Test mission. This agent supports the general department in achieving its "
            "objectives. It operates with precision and efficiency to fulfill assigned tasks.\n\n"
            "RESPONSIBILITIES:\n"
            "1. Parse and validate incoming task specifications for the general department.\n"
            "2. Retrieve and manage files and records using filesystem_server and registry_server.\n"
            "3. Execute assigned workflows in strict accordance with the execution_workflow sequence.\n"
            "4. Apply decision_rules consistently at every action point during task execution.\n"
            "5. Produce structured, validated outputs that meet quality_standards benchmarks.\n"
            "6. Generate and persist audit logs for all state-changing operations.\n"
            "7. Emit completion reports and escalation notices via the defined communication_protocol.\n"
            "8. Maintain operational scope strictly within the general department boundaries.\n\n"
            "DECISION RULES:\n"
            "- Always verify department scope before acting.\n"
            "- Prefer read operations before write operations to confirm current state.\n"
            "- If a required resource is missing, log the gap and continue with available data.\n"
            "- Never modify data outside the general department's designated paths or keys.\n"
            "- Escalate immediately if a task cannot be completed within defined boundaries.\n\n"
            "QUALITY STANDARDS:\n"
            "- All outputs must be structured and machine-parseable (JSON preferred).\n"
            "- Every state-changing operation must be accompanied by an audit entry.\n"
            "- Responses must be concise, accurate, and free of speculation.\n\n"
            "ALLOWED TOOLS: filesystem_server, registry_server.\n"
            "Do not attempt to use any tool not listed above."
        )

    def _build_user_message(self, task_spec: TaskSpec) -> str:
        """
        Construct the initial user message from the validated task specification.

        Parameters
        ----------
        task_spec : TaskSpec
            Validated task specification.

        Returns
        -------
        str
            Formatted user message string.
        """
        return (
            f"Task ID: {task_spec.task_id}\n"
            f"Department: {task_spec.department}\n"
            f"Priority: {task_spec.priority}\n"
            f"Description: {task_spec.description}\n"
            f"Payload: {json.dumps(task_spec.payload, indent=2)}\n\n"
            "Please execute this task according to your responsibilities and decision rules. "
            "Use the available tools as needed and provide a structured summary of the outcome."
        )

    @staticmethod
    def _tool_definitions() -> list[dict]:
        """
        Return Anthropic-compatible tool definitions for filesystem_server and registry_server.

        Returns
        -------
        list[dict]
            List of tool definition dictionaries.
        """
        return [
            {
                "name": "filesystem_server",
                "description": (
                    "Perform file system operations: read_file, write_file, "
                    "list_directory, delete_file."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read_file", "write_file", "list_directory", "delete_file"],
                            "description": "The filesystem operation to perform.",
                        },
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative file/directory path.",
                        },
                        "content": {
                            "type": "string",
                            "description": "File content for write_file operations.",
                        },
                    },
                    "required": ["operation", "path"],
                },
            },
            {
                "name": "registry_server",
                "description": (
                    "Perform registry (key-value store) operations: "
                    "get_record, set_record, delete_record, list_keys."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["get_record", "set_record", "delete_record", "list_keys"],
                            "description": "The registry operation to perform.",
                        },
                        "key": {
                            "type": "string",
                            "description": "Registry key (required for get/set/delete).",
                        },
                        "value": {
                            "description": "Value to store (required for set_record).",
                        },
                    },
                    "required": ["operation"],
                },
            },
        ]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string with timezone info."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    """Run a smoke-test task when the module is executed directly."""
    agent = ExistsAgentC9117575()
    sample_task = json.dumps(
        {
            "task_id": "smoke-test-001",
            "description": "List the current working directory and store the result in the registry.",
            "department": "general",
            "priority": "normal",
            "payload": {"target_path": "."},
        }
    )
    result = await agent.run(sample_task)
    print(result)


if __name__ == "__main__":
    asyncio.run(_main())