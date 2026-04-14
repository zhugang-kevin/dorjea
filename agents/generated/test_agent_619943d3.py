import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Any

import anthropic
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskSpec(BaseModel):
    """Represents a validated task specification document."""

    task_id: str = Field(default_factory=lambda: f"task_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    description: str
    priority: str = "normal"
    retry_limit: int = 3
    token_budget: int = 50000


class RunRecord(BaseModel):
    """Tracks execution history for a single run."""

    run_id: str
    task_id: str
    status: str
    start_time: str
    end_time: str = ""
    outcome: str = ""
    anomalies: list[str] = Field(default_factory=list)
    tokens_used: int = 0


class TestAgent619943D3:
    """
    AI agent for the general department responsible for executing test cases,
    managing filesystem artifacts, maintaining registry entries, and emitting
    structured reports. Operates with precision and reliability using
    filesystem_server and registry_server tools via the Anthropic API.
    """

    TOOLS = [
        {
            "name": "filesystem_server",
            "description": (
                "Interact with the filesystem to create, read, update, delete, "
                "and version files and directories. Supports artifact management "
                "for test inputs and outputs."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "delete", "list", "exists", "version"],
                        "description": "The filesystem operation to perform.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the target file or directory.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (required for write operation).",
                    },
                    "version_tag": {
                        "type": "string",
                        "description": "Version label for versioning operations.",
                    },
                },
                "required": ["operation", "path"],
            },
        },
        {
            "name": "registry_server",
            "description": (
                "Manage agent registry entries including state, run history, "
                "health status, and configuration metadata."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["get", "set", "update", "delete", "list", "health_check"],
                        "description": "The registry operation to perform.",
                    },
                    "key": {
                        "type": "string",
                        "description": "Registry key to operate on.",
                    },
                    "value": {
                        "type": "object",
                        "description": "Value to store (required for set/update operations).",
                    },
                },
                "required": ["operation", "key"],
            },
        },
    ]

    def __init__(self) -> None:
        """
        Initialize the agent by reading all configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic client authentication.

        Optional environment variables:
            AGENT_MODEL: Model identifier (default: claude-sonnet-4-6).
            AGENT_MAX_TOKENS: Maximum tokens per response (default: 4096).
            AGENT_RETRY_LIMIT: Max retries on transient failures (default: 3).
            AGENT_RETRY_BACKOFF: Base backoff seconds between retries (default: 2.0).
            AGENT_TOKEN_BUDGET: Total token budget for the session (default: 50000).
            AGENT_DEPARTMENT: Department this agent serves (default: general).
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is required.")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        self.retry_limit = int(os.getenv("AGENT_RETRY_LIMIT", "3"))
        self.retry_backoff = float(os.getenv("AGENT_RETRY_BACKOFF", "2.0"))
        self.token_budget = int(os.getenv("AGENT_TOKEN_BUDGET", "50000"))
        self.department = os.getenv("AGENT_DEPARTMENT", "general")

        self.agent_name = "test_agent_619943d3"
        self.tokens_used = 0
        self.anomalies: list[str] = []
        self.run_history: list[RunRecord] = []

        self.system_prompt = (
            f"You are {self.agent_name}, an AI agent serving the {self.department} department. "
            "Your mission: Test mission for automated testing. This agent supports the general "
            "department in executing its core responsibilities. It operates with precision and "
            "reliability to fulfill assigned objectives.\n\n"
            "Your responsibilities:\n"
            "1. Parse and validate incoming TaskSpec documents for completeness and correctness "
            "before execution begins.\n"
            "2. Execute assigned test cases in the correct dependency order and record granular "
            "pass/fail outcomes.\n"
            "3. Manage all filesystem artifacts including creation, versioning, and cleanup of "
            "test inputs and outputs.\n"
            "4. Maintain accurate and current registry entries reflecting agent state, run "
            "history, and health status.\n"
            "5. Detect and log all anomalies, deviations, and unexpected behaviors encountered "
            "during execution.\n"
            "6. Emit structured completion and escalation reports conforming to the defined "
            "communication protocol.\n"
            "7. Enforce retry logic and backoff policies on transient tool failures before "
            "escalating.\n"
            "8. Track and respect token budget utilization throughout the session lifecycle.\n\n"
            "Always use the available tools (filesystem_server, registry_server) to complete "
            "tasks. Emit structured JSON reports upon completion. Log anomalies explicitly."
        )

    def _validate_task_spec(self, task: str) -> TaskSpec:
        """
        Parse and validate the incoming task string into a TaskSpec document.

        Args:
            task: Raw task description string or JSON-encoded TaskSpec.

        Returns:
            A validated TaskSpec instance.

        Raises:
            ValueError: If the task string is empty or cannot be parsed.
        """
        if not task or not task.strip():
            raise ValueError("Task description must not be empty.")

        try:
            data = json.loads(task)
            spec = TaskSpec(**data)
        except (json.JSONDecodeError, TypeError):
            spec = TaskSpec(description=task.strip())

        logger.info("TaskSpec validated: task_id=%s", spec.task_id)
        return spec

    def _check_token_budget(self) -> bool:
        """
        Check whether the current token usage is within the allowed budget.

        Returns:
            True if within budget, False if budget is exhausted.
        """
        remaining = self.token_budget - self.tokens_used
        if remaining <= 0:
            self._record_anomaly("Token budget exhausted.")
            logger.warning("Token budget exhausted: used=%d, budget=%d", self.tokens_used, self.token_budget)
            return False
        logger.debug("Token budget check: used=%d, remaining=%d", self.tokens_used, remaining)
        return True

    def _record_anomaly(self, message: str) -> None:
        """
        Record an anomaly or unexpected behavior encountered during execution.

        Args:
            message: Human-readable description of the anomaly.
        """
        timestamp = datetime.utcnow().isoformat()
        entry = f"[{timestamp}] {message}"
        self.anomalies.append(entry)
        logger.warning("ANOMALY: %s", entry)

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Simulate processing a tool call by returning a structured mock response.

        In production this method would dispatch to actual tool servers. Here it
        returns realistic structured responses so the agent loop can proceed.

        Args:
            tool_name: Name of the tool being invoked.
            tool_input: Input parameters for the tool call.

        Returns:
            JSON string representing the tool's response.
        """
        operation = tool_input.get("operation", "unknown")
        path_or_key = tool_input.get("path") or tool_input.get("key", "unknown")

        if tool_name == "filesystem_server":
            if operation == "write":
                result = {"status": "success", "path": path_or_key, "bytes_written": len(tool_input.get("content", ""))}
            elif operation == "read":
                result = {"status": "success", "path": path_or_key, "content": f"<content of {path_or_key}>"}
            elif operation == "list":
                result = {"status": "success", "path": path_or_key, "entries": []}
            elif operation == "exists":
                result = {"status": "success", "path": path_or_key, "exists": True}
            elif operation == "delete":
                result = {"status": "success", "path": path_or_key, "deleted": True}
            elif operation == "version":
                result = {
                    "status": "success",
                    "path": path_or_key,
                    "version_tag": tool_input.get("version_tag", "v1"),
                }
            else:
                result = {"status": "error", "message": f"Unknown operation: {operation}"}

        elif tool_name == "registry_server":
            if operation in ("set", "update"):
                result = {"status": "success", "key": path_or_key, "stored": True}
            elif operation == "get":
                result = {"status": "success", "key": path_or_key, "value": {}}
            elif operation == "list":
                result = {"status": "success", "keys": []}
            elif operation == "delete":
                result = {"status": "success", "key": path_or_key, "deleted": True}
            elif operation == "health_check":
                result = {"status": "success", "healthy": True, "latency_ms": 5}
            else:
                result = {"status": "error", "message": f"Unknown operation: {operation}"}
        else:
            result = {"status": "error", "message": f"Unknown tool: {tool_name}"}

        return json.dumps(result)

    def _call_api_with_retry(self, messages: list[dict[str, Any]]) -> anthropic.types.Message:
        """
        Call the Anthropic API with retry logic and exponential backoff.

        Args:
            messages: List of message dicts to send to the model.

        Returns:
            The API response Message object.

        Raises:
            RuntimeError: If all retry attempts are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.retry_limit + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    tools=self.TOOLS,
                    messages=messages,
                )
                return response
            except anthropic.RateLimitError as exc:
                last_exception = exc
                wait = self.retry_backoff * (2 ** (attempt - 1))
                self._record_anomaly(f"Rate limit hit on attempt {attempt}. Backing off {wait}s.")
                logger.warning("Rate limit on attempt %d/%d. Sleeping %.1fs.", attempt, self.retry_limit, wait)
                asyncio.get_event_loop().run_until_complete(asyncio.sleep(wait))
            except anthropic.APIStatusError as exc:
                last_exception = exc
                if exc.status_code and exc.status_code >= 500:
                    wait = self.retry_backoff * (2 ** (attempt - 1))
                    self._record_anomaly(f"Server error {exc.status_code} on attempt {attempt}. Backing off {wait}s.")
                    logger.warning("Server error %d on attempt %d/%d. Sleeping %.1fs.", exc.status_code, attempt, self.retry_limit, wait)
                    asyncio.get_event_loop().run_until_complete(asyncio.sleep(wait))
                else:
                    raise
            except Exception as exc:
                last_exception = exc
                self._record_anomaly(f"Unexpected API error on attempt {attempt}: {exc}")
                raise

        raise RuntimeError(f"All {self.retry_limit} API retry attempts exhausted. Last error: {last_exception}")

    def _build_completion_report(self, spec: TaskSpec, record: RunRecord) -> str:
        """
        Build a structured JSON completion report conforming to the communication protocol.

        Args:
            spec: The validated TaskSpec that was executed.
            record: The RunRecord capturing execution details.

        Returns:
            JSON string of the completion report.
        """
        report = {
            "report_type": "completion",
            "agent": self.agent_name,
            "department": self.department,
            "task_id": spec.task_id,
            "run_id": record.run_id,
            "status": record.status,
            "outcome": record.outcome,
            "start_time": record.start_time,
            "end_time": record.end_time,
            "tokens_used": record.tokens_used,
            "token_budget": self.token_budget,
            "anomalies": record.anomalies,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return json.dumps(report, indent=2)

    async def run(self, task: str) -> str:
        """
        Execute the agent's main agentic loop for the given task.

        Validates the task spec, runs the model in a tool-use loop until the
        model signals completion, manages filesystem and registry artifacts,
        tracks token usage, records anomalies, and returns a structured
        completion report.

        Args:
            task: Raw task description or JSON-encoded TaskSpec document.

        Returns:
            A JSON-formatted completion report string.
        """
        start_time = datetime.utcnow().isoformat()
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

        try:
            spec = self._validate_task_spec(task)
        except ValueError as exc:
            self._record_anomaly(f"TaskSpec validation failed: {exc}")
            return json.dumps({
                "report_type": "escalation",
                "agent": self.agent_name,
                "error": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
            })

        record = RunRecord(
            run_id=run_id,
            task_id=spec.task_id,
            status="running",
            start_time=start_time,
        )

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"Execute the following task with task_id={spec.task_id}:\n\n"
                    f"{spec.description}\n\n"
                    f"Priority: {spec.priority}. Token budget: {self.token_budget}. "
                    "Use filesystem_server and registry_server tools as needed. "
                    "Upon completion, emit a structured JSON summary of what was done."
                ),
            }
        ]

        final_text = ""

        try:
            while True:
                if not self._check_token_budget():
                    record.status = "failed"
                    record.outcome = "Token budget exhausted before completion."
                    break

                try:
                    response = self._call_api_with_retry(messages)
                except RuntimeError as exc:
                    self._record_anomaly(f"API call failed after retries: {exc}")
                    record.status = "failed"
                    record.outcome = str(exc)
                    break

                input_tokens = getattr(response.usage, "input_tokens", 0)
                output_tokens = getattr(response.usage, "output_tokens", 0)
                self.tokens_used += input_tokens + output_tokens
                record.tokens_used = self.tokens_used

                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text = block.text
                    record.status = "success"
                    record.outcome = final_text or "Task completed successfully."
                    break

                if response.stop_reason == "tool_use":
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.content,
                    }
                    messages.append(assistant_message)

                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id

                            logger.info("Tool call: %s | input=%s", tool_name, json.dumps(tool_input))

                            try:
                                tool_result = self._process_tool_call(tool_name, tool_input)
                            except Exception as exc:
                                self._record_anomaly(f"Tool {tool_name} raised exception: {exc}")
                                tool_result = json.dumps({"status": "error", "message": str(exc)})

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": tool_result,
                            })

                    messages.append({"role": "user", "content": tool_results})
                    continue

                self._record_anomaly(f"Unexpected stop_reason: {response.stop_reason}")
                record.status = "failed"
                record.outcome = f"Unexpected stop_reason: {response.stop_reason}"
                break

        except Exception as exc:
            self._record_anomaly(f"Unhandled exception in run loop: {exc}")
            record.status = "failed"
            record.outcome = str(exc)
            logger.exception("Unhandled exception in agent run loop.")

        record.end_time = datetime.utcnow().isoformat()
        record.anomalies = list(self.anomalies)
        self.run_history.append(record)

        return self._build_completion_report(spec, record)


if __name__ == "__main__":
    async def main() -> None:
        """Entry point for running the agent from the command line."""
        agent = TestAgent619943D3()
        result = await agent.run(
            "Run the standard smoke test suite, validate all outputs, "
            "and update the registry with the final health status."
        )
        print(result)

    asyncio.run(main())