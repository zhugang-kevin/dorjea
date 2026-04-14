import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("a00f072c_agent")


class TaskPayload(BaseModel):
    """Validated structure for incoming task payloads."""

    task: str
    priority: str = "normal"
    metadata: dict[str, Any] = {}


class ExecutionReport(BaseModel):
    """Structured report produced after each execution cycle."""

    agent_id: str
    task: str
    status: str
    result: str
    timestamp: str
    token_usage: dict[str, int]
    errors: list[str]


class A00F072CAgent:
    """
    Agent a00f072c for the general department.

    Mission: Test mission for automated testing. This agent supports the
    general department with its core responsibilities. It operates with
    precision and efficiency to fulfill its designated objectives.

    Responsibilities:
    - Execute automated test tasks assigned by the general department orchestrator
    - Validate all input payloads before processing
    - Retrieve and manage test artifacts via filesystem_server
    - Query and update agent and resource metadata in registry_server
    - Produce structured, timestamped test reports after each execution cycle
    - Apply all decision rules consistently to handle errors and edge cases
    - Monitor token usage and adapt task prioritization within token_budget
    - Escalate qualifying conditions per escalation_triggers
    """

    AGENT_ID = "a00f072c_agent"
    DEPARTMENT = "general"
    MODEL = "claude-sonnet-4-6"

    def __init__(self) -> None:
        """
        Initialize the agent, reading all configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude.
            TOKEN_BUDGET: Maximum tokens allowed per execution cycle (default: 8192).
            ESCALATION_THRESHOLD: Error count that triggers escalation (default: 3).
            FILESYSTEM_SERVER_PATH: Base path for filesystem_server artifact storage.
            REGISTRY_SERVER_URL: URL or path for registry_server metadata store.
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")

        self.token_budget = int(os.getenv("TOKEN_BUDGET", "8192"))
        self.escalation_threshold = int(os.getenv("ESCALATION_THRESHOLD", "3"))
        self.filesystem_server_path = os.getenv(
            "FILESYSTEM_SERVER_PATH", "/tmp/a00f072c_artifacts"
        )
        self.registry_server_url = os.getenv(
            "REGISTRY_SERVER_URL", "/tmp/a00f072c_registry"
        )

        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.tools = self._define_tools()
        self.errors: list[str] = []
        self.token_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

        logger.info(
            "Agent %s initialized for department '%s'.", self.AGENT_ID, self.DEPARTMENT
        )

    def _define_tools(self) -> list[dict[str, Any]]:
        """
        Define the tool schemas for filesystem_server and registry_server.

        Returns:
            List of tool definition dicts compatible with the Anthropic API.
        """
        return [
            {
                "name": "filesystem_server",
                "description": (
                    "Interact with the filesystem server to read, write, list, or delete "
                    "test artifacts. Follows department naming and versioning conventions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list", "delete"],
                            "description": "The filesystem operation to perform.",
                        },
                        "path": {
                            "type": "string",
                            "description": "Relative path within the artifact store.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write (required for 'write' operation).",
                        },
                    },
                    "required": ["operation", "path"],
                },
            },
            {
                "name": "registry_server",
                "description": (
                    "Query or update agent and resource metadata in the registry server "
                    "to maintain accurate operational state."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["get", "set", "list", "delete"],
                            "description": "The registry action to perform.",
                        },
                        "key": {
                            "type": "string",
                            "description": "Registry key to operate on.",
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to store (required for 'set' action).",
                        },
                    },
                    "required": ["action", "key"],
                },
            },
        ]

    def _validate_task(self, task: str) -> TaskPayload:
        """
        Validate and parse the incoming task string into a TaskPayload.

        Attempts JSON parsing first; falls back to treating the raw string as the task.

        Args:
            task: Raw task string from the orchestrator.

        Returns:
            A validated TaskPayload instance.

        Raises:
            ValueError: If the task string is empty or cannot be validated.
        """
        if not task or not task.strip():
            raise ValueError("Task string must not be empty.")

        try:
            data = json.loads(task)
            payload = TaskPayload(**data)
        except (json.JSONDecodeError, ValidationError):
            payload = TaskPayload(task=task.strip())

        logger.info("Task validated: priority=%s", payload.priority)
        return payload

    def _execute_filesystem_server(self, operation: str, path: str, content: str = "") -> str:
        """
        Execute a filesystem_server tool call locally.

        Args:
            operation: One of 'read', 'write', 'list', 'delete'.
            path: Relative path within the artifact store.
            content: Content to write (only for 'write' operation).

        Returns:
            String result of the operation.
        """
        import os as _os

        base = self.filesystem_server_path
        full_path = _os.path.join(base, path.lstrip("/"))

        try:
            if operation == "list":
                target = full_path if _os.path.isdir(full_path) else base
                if _os.path.isdir(target):
                    entries = _os.listdir(target)
                    return json.dumps(entries)
                return json.dumps([])

            elif operation == "read":
                if _os.path.isfile(full_path):
                    with open(full_path, "r", encoding="utf-8") as fh:
                        return fh.read()
                return f"File not found: {path}"

            elif operation == "write":
                _os.makedirs(_os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                return f"Written successfully: {path}"

            elif operation == "delete":
                if _os.path.isfile(full_path):
                    _os.remove(full_path)
                    return f"Deleted: {path}"
                return f"File not found for deletion: {path}"

            else:
                return f"Unknown operation: {operation}"

        except OSError as exc:
            error_msg = f"filesystem_server error ({operation} '{path}'): {exc}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return error_msg

    def _execute_registry_server(self, action: str, key: str, value: str = "") -> str:
        """
        Execute a registry_server tool call using a local JSON file as the registry store.

        Args:
            action: One of 'get', 'set', 'list', 'delete'.
            key: Registry key to operate on.
            value: Value to store (only for 'set' action).

        Returns:
            String result of the action.
        """
        import os as _os

        registry_file = _os.path.join(self.registry_server_url, "registry.json")
        _os.makedirs(self.registry_server_url, exist_ok=True)

        registry: dict[str, str] = {}
        try:
            if _os.path.isfile(registry_file):
                with open(registry_file, "r", encoding="utf-8") as fh:
                    registry = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load registry: %s", exc)

        try:
            if action == "get":
                return registry.get(key, f"Key not found: {key}")

            elif action == "set":
                registry[key] = value
                with open(registry_file, "w", encoding="utf-8") as fh:
                    json.dump(registry, fh, indent=2)
                return f"Registry key '{key}' set successfully."

            elif action == "list":
                return json.dumps(list(registry.keys()))

            elif action == "delete":
                if key in registry:
                    del registry[key]
                    with open(registry_file, "w", encoding="utf-8") as fh:
                        json.dump(registry, fh, indent=2)
                    return f"Registry key '{key}' deleted."
                return f"Key not found for deletion: {key}"

            else:
                return f"Unknown action: {action}"

        except OSError as exc:
            error_msg = f"registry_server error ({action} '{key}'): {exc}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return error_msg

    def _dispatch_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Dispatch a tool call to the appropriate local handler.

        Args:
            tool_name: Name of the tool ('filesystem_server' or 'registry_server').
            tool_input: Dictionary of input parameters for the tool.

        Returns:
            String result from the tool handler.
        """
        if tool_name == "filesystem_server":
            return self._execute_filesystem_server(
                operation=tool_input.get("operation", "list"),
                path=tool_input.get("path", ""),
                content=tool_input.get("content", ""),
            )
        elif tool_name == "registry_server":
            return self._execute_registry_server(
                action=tool_input.get("action", "get"),
                key=tool_input.get("key", ""),
                value=tool_input.get("value", ""),
            )
        else:
            msg = f"Unknown tool requested: {tool_name}"
            logger.warning(msg)
            return msg

    def _check_escalation(self) -> bool:
        """
        Determine whether current error count meets the escalation threshold.

        Returns:
            True if escalation should be triggered, False otherwise.
        """
        return len(self.errors) >= self.escalation_threshold

    def _check_token_budget(self) -> bool:
        """
        Check whether total token usage is within the configured budget.

        Returns:
            True if within budget, False if budget is exceeded.
        """
        total = self.token_usage["input_tokens"] + self.token_usage["output_tokens"]
        return total < self.token_budget

    def _build_report(self, task: str, status: str, result: str) -> ExecutionReport:
        """
        Build a structured, timestamped execution report.

        Args:
            task: The original task string.
            status: Execution status ('success', 'partial', 'failed', 'escalated').
            result: Final result or summary string.

        Returns:
            A populated ExecutionReport instance.
        """
        return ExecutionReport(
            agent_id=self.AGENT_ID,
            task=task,
            status=status,
            result=result,
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_usage=dict(self.token_usage),
            errors=list(self.errors),
        )

    def _persist_report(self, report: ExecutionReport) -> None:
        """
        Persist the execution report to the filesystem artifact store.

        Args:
            report: The ExecutionReport to save.
        """
        filename = f"report_{report.timestamp.replace(':', '-').replace('.', '-')}.json"
        try:
            self._execute_filesystem_server(
                operation="write",
                path=f"reports/{filename}",
                content=report.model_dump_json(indent=2),
            )
            logger.info("Report persisted: reports/%s", filename)
        except Exception as exc:
            logger.error("Failed to persist report: %s", exc)

    def _update_registry_state(self, status: str) -> None:
        """
        Update the agent's operational state in the registry server.

        Args:
            status: Current execution status to record.
        """
        try:
            self._execute_registry_server(
                action="set",
                key=f"{self.AGENT_ID}/last_status",
                value=status,
            )
            self._execute_registry_server(
                action="set",
                key=f"{self.AGENT_ID}/last_run",
                value=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("Failed to update registry state: %s", exc)

    async def run(self, task: str) -> str:
        """
        Execute the agent's main agentic loop for the given task.

        Validates the input, runs the Claude model with tool-use in an agentic
        loop, dispatches tool calls, monitors token budget, checks escalation
        conditions, produces a structured report, and returns the final result.

        Args:
            task: The task string assigned by the general department orchestrator.

        Returns:
            JSON-serialized ExecutionReport string summarizing the execution.
        """
        self.errors = []
        self.token_usage = {"input_tokens": 0, "output_tokens": 0}

        # Validate input payload
        try:
            payload = self._validate_task(task)
        except ValueError as exc:
            logger.error("Task validation failed: %s", exc)
            report = self._build_report(task, "failed", str(exc))
            self._persist_report(report)
            return report.model_dump_json(indent=2)

        system_prompt = (
            f"You are agent {self.AGENT_ID}, operating in the '{self.DEPARTMENT}' department. "
            "Your mission: Test mission for automated testing. This agent supports the general "
            "department with its core responsibilities. It operates with precision and efficiency "
            "to fulfill its designated objectives.\n\n"
            "Responsibilities:\n"
            "- Execute automated test tasks assigned by the general department orchestrator with full fidelity\n"
            "- Validate all input payloads before processing to prevent downstream errors\n"
            "- Retrieve and manage test artifacts via filesystem_server following naming conventions\n"
            "- Query and update agent and resource metadata in registry_server\n"
            "- Produce structured, timestamped test reports after each execution cycle\n"
            "- Apply all decision rules consistently to handle errors and edge cases\n"
            "- Monitor token usage and adapt task prioritization within budget\n"
            "- Escalate qualifying conditions promptly per escalation_triggers\n\n"
            f"Token budget: {self.token_budget} total tokens. Prioritize efficiency.\n"
            "Use the available tools as needed to complete the task thoroughly."
        )

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": payload.task}
        ]

        final_result = ""
        status = "success"

        # Agentic loop
        while True:
            if not self._check_token_budget():
                logger.warning("Token budget exceeded. Stopping execution.")
                self.errors.append("Token budget exceeded during execution.")
                status = "partial"
                final_result = final_result or "Execution halted: token budget exceeded."
                break

            if self._check_escalation():
                logger.warning("Escalation threshold reached (%d errors).", len(self.errors))
                status = "escalated"
                final_result = (
                    f"Escalation triggered after {len(self.errors)} errors: "
                    + "; ".join(self.errors)
                )
                break

            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.MODEL,
                    max_tokens=min(4096, self.token_budget - self.token_usage["input_tokens"]),
                    system=system_prompt,
                    tools=self.tools,
                    messages=messages,
                )
            except anthropic.APIConnectionError as exc:
                error_msg = f"API connection error: {exc}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                status = "failed"
                final_result = error_msg
                break
            except anthropic.RateLimitError as exc:
                error_msg = f"Rate limit error: {exc}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                status = "failed"
                final_result = error_msg
                break
            except anthropic.APIStatusError as exc:
                error_msg = f"API status error {exc.status_code}: {exc.message}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                status = "failed"
                final_result = error_msg
                break
            except Exception as exc:
                error_msg = f"Unexpected error during API call: {exc}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                status = "failed"
                final_result = error_msg
                break

            # Accumulate token usage
            self.token_usage["input_tokens"] += response.usage.input_tokens
            self.token_usage["output_tokens"] += response.usage.output_tokens

            logger.info(
                "API response: stop_reason=%s, tokens used: in=%d out=%d",
                response.stop_reason,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            # Collect assistant message content
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn":
                # Extract final text result
                for block in assistant_content:
                    if hasattr(block, "text"):
                        final_result = block.text
                        break
                break

            elif response.stop_reason == "tool_use":
                # Process all tool calls in this response
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        logger.info("Tool call: %s with input %s", block.name, block.input)
                        tool_output = self._dispatch_tool(block.name, block.input)
                        logger.info("Tool result for %s: %s", block.name, tool_output[:200])
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_output,
                            }
                        )

                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                logger.warning("Unexpected stop_reason: %s", response.stop_reason)
                for block in assistant_content:
                    if hasattr(block, "text"):
                        final_result = block.text
                        break
                break

        if not final_result:
            final_result = "Task completed with no textual output."
            if self.errors:
                status = "partial"

        # Update registry with final state
        self._update_registry_state(status)

        # Build and persist report
        report = self._build_report(task, status, final_result)
        self._persist_report(report)

        logger.info(
            "Agent %s finished. Status=%s, total_tokens=%d",
            self.AGENT_ID,
            status,
            self.token_usage["input_tokens"] + self.token_usage["output_tokens"],
        )

        return report.model_dump_json(indent=2)


async def main() -> None:
    """Entry point for running the agent from the command line."""
    agent = A00F072CAgent()
    sample_task = json.dumps(
        {
            "task": "Run a diagnostic check: list all artifacts in the filesystem store, "
                    "verify the agent registry entry exists, and confirm operational readiness.",
            "priority": "high",
            "metadata": {"requested_by": "orchestrator", "cycle": 1},
        }
    )
    result = await agent.run(sample_task)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())