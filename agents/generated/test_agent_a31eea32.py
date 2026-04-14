import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic
from pydantic import BaseModel, Field


class TaskRecord(BaseModel):
    """Immutable record of a task execution outcome."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = "test_agent_a31eea32"
    department: str = "general"
    task_input: str = ""
    task_output: str = ""
    status: str = "pending"
    start_time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    end_time: str = ""
    retry_count: int = 0
    escalated: bool = False
    anomalies: list[str] = Field(default_factory=list)
    verification_passed: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)


class ObservabilityLogger:
    """Structured observability logger for task lifecycle events."""

    def __init__(self, agent_name: str, department: str):
        """Initialize the observability logger.

        Args:
            agent_name: Name of the agent emitting logs.
            department: Department the agent belongs to.
        """
        self.agent_name = agent_name
        self.department = department
        self.logger = logging.getLogger(agent_name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def emit(self, event: str, task_id: str, data: dict[str, Any] | None = None):
        """Emit a structured observability log entry.

        Args:
            event: The lifecycle event name.
            task_id: Unique identifier for the task.
            data: Additional structured data to include in the log.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_name,
            "department": self.department,
            "event": event,
            "task_id": task_id,
            "data": data or {},
        }
        self.logger.info(json.dumps(log_entry))


class TestAgentA31Eea32:
    """
    Agent for the general department.

    Mission: Test mission for automated testing. This agent supports the general
    department in executing its core responsibilities. It operates with precision
    and reliability to fulfill its designated objectives.

    Responsibilities:
    - Receive, validate, and execute assigned tasks within the general department scope
    - Maintain accurate and up-to-date task state records in the registry and filesystem
    - Apply defined decision rules consistently across all task executions
    - Emit structured observability logs and metrics for every task lifecycle event
    - Evaluate and enforce escalation triggers at task conclusion or upon failure
    - Produce completion reports documenting inputs, outputs, verification results, and anomalies
    - Adhere strictly to retry policy parameters during transient failure recovery
    - Support audit and compliance requirements by preserving immutable task outcome records
    """

    def __init__(self):
        """Initialize the agent by reading all configuration from environment variables."""
        self.agent_name = "test_agent_a31eea32"
        self.department = "general"
        self.model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.max_retries = int(os.getenv("AGENT_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("AGENT_RETRY_DELAY", "1.0"))
        self.escalation_threshold = int(os.getenv("AGENT_ESCALATION_THRESHOLD", "2"))
        self.max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        self.filesystem_base_path = os.getenv("AGENT_FILESYSTEM_PATH", "/tmp/agent_records")
        self.registry_path = os.getenv("AGENT_REGISTRY_PATH", "/tmp/agent_registry")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.obs_logger = ObservabilityLogger(self.agent_name, self.department)

        self.tools = [
            {
                "name": "filesystem_server",
                "description": "Read and write files to the filesystem for task records and outputs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list"],
                            "description": "The filesystem operation to perform.",
                        },
                        "path": {
                            "type": "string",
                            "description": "The file path for the operation.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write (required for write operation).",
                        },
                    },
                    "required": ["operation", "path"],
                },
            },
            {
                "name": "registry_server",
                "description": "Manage task state records in the registry.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["get", "set", "delete", "list"],
                            "description": "The registry operation to perform.",
                        },
                        "key": {
                            "type": "string",
                            "description": "The registry key.",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value to store (required for set operation).",
                        },
                    },
                    "required": ["operation", "key"],
                },
            },
        ]

        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required filesystem directories exist."""
        try:
            os.makedirs(self.filesystem_base_path, exist_ok=True)
            os.makedirs(self.registry_path, exist_ok=True)
        except OSError as e:
            self.obs_logger.emit(
                "directory_creation_failed",
                "init",
                {"error": str(e)},
            )

    def _execute_filesystem_operation(
        self, operation: str, path: str, content: str | None = None
    ) -> str:
        """Execute a filesystem operation.

        Args:
            operation: The operation to perform (read, write, list).
            path: The file path for the operation.
            content: Content to write for write operations.

        Returns:
            Result of the filesystem operation as a string.
        """
        try:
            full_path = os.path.join(self.filesystem_base_path, path.lstrip("/"))
            if operation == "write":
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content or "")
                return f"Successfully wrote to {path}"
            elif operation == "read":
                if os.path.exists(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        return f.read()
                return f"File not found: {path}"
            elif operation == "list":
                if os.path.exists(full_path):
                    files = os.listdir(full_path)
                    return json.dumps(files)
                return json.dumps([])
            else:
                return f"Unknown operation: {operation}"
        except OSError as e:
            return f"Filesystem error: {str(e)}"

    def _execute_registry_operation(
        self, operation: str, key: str, value: str | None = None
    ) -> str:
        """Execute a registry operation.

        Args:
            operation: The operation to perform (get, set, delete, list).
            key: The registry key.
            value: The value to store for set operations.

        Returns:
            Result of the registry operation as a string.
        """
        try:
            registry_file = os.path.join(self.registry_path, "registry.json")
            registry = {}
            if os.path.exists(registry_file):
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)

            if operation == "set":
                registry[key] = value
                with open(registry_file, "w", encoding="utf-8") as f:
                    json.dump(registry, f, indent=2)
                return f"Successfully set key: {key}"
            elif operation == "get":
                return registry.get(key, f"Key not found: {key}")
            elif operation == "delete":
                if key in registry:
                    del registry[key]
                    with open(registry_file, "w", encoding="utf-8") as f:
                        json.dump(registry, f, indent=2)
                    return f"Successfully deleted key: {key}"
                return f"Key not found: {key}"
            elif operation == "list":
                return json.dumps(list(registry.keys()))
            else:
                return f"Unknown operation: {operation}"
        except (OSError, json.JSONDecodeError) as e:
            return f"Registry error: {str(e)}"

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Process a tool call and return the result.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Result of the tool execution as a string.
        """
        try:
            if tool_name == "filesystem_server":
                return self._execute_filesystem_operation(
                    operation=tool_input.get("operation", ""),
                    path=tool_input.get("path", ""),
                    content=tool_input.get("content"),
                )
            elif tool_name == "registry_server":
                return self._execute_registry_operation(
                    operation=tool_input.get("operation", ""),
                    key=tool_input.get("key", ""),
                    value=tool_input.get("value"),
                )
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool execution error: {str(e)}"

    def _validate_task(self, task: str) -> tuple[bool, str]:
        """Validate the incoming task.

        Args:
            task: The task string to validate.

        Returns:
            Tuple of (is_valid, validation_message).
        """
        if not task or not task.strip():
            return False, "Task cannot be empty"
        if len(task) > 10000:
            return False, "Task exceeds maximum length of 10000 characters"
        return True, "Task is valid"

    def _should_escalate(self, record: TaskRecord) -> bool:
        """Evaluate whether a task should be escalated.

        Args:
            record: The task record to evaluate.

        Returns:
            True if the task should be escalated, False otherwise.
        """
        if record.retry_count >= self.escalation_threshold:
            return True
        if record.status == "failed" and len(record.anomalies) > 0:
            return True
        return False

    def _save_task_record(self, record: TaskRecord):
        """Save an immutable task record to the filesystem.

        Args:
            record: The task record to save.
        """
        try:
            record_path = os.path.join(
                self.filesystem_base_path,
                "task_records",
                f"{record.task_id}.json",
            )
            os.makedirs(os.path.dirname(record_path), exist_ok=True)
            with open(record_path, "w", encoding="utf-8") as f:
                json.dump(record.model_dump(), f, indent=2)
        except OSError as e:
            self.obs_logger.emit(
                "record_save_failed",
                record.task_id,
                {"error": str(e)},
            )

    def _update_registry(self, record: TaskRecord):
        """Update the registry with the current task state.

        Args:
            record: The task record to register.
        """
        try:
            self._execute_registry_operation(
                operation="set",
                key=f"task:{record.task_id}",
                value=json.dumps(
                    {
                        "status": record.status,
                        "start_time": record.start_time,
                        "end_time": record.end_time,
                        "escalated": record.escalated,
                    }
                ),
            )
        except Exception as e:
            self.obs_logger.emit(
                "registry_update_failed",
                record.task_id,
                {"error": str(e)},
            )

    def _generate_completion_report(self, record: TaskRecord) -> str:
        """Generate a completion report for the task.

        Args:
            record: The completed task record.

        Returns:
            Formatted completion report as a string.
        """
        report = {
            "report_type": "task_completion",
            "agent": self.agent_name,
            "department": self.department,
            "task_id": record.task_id,
            "summary": {
                "status": record.status,
                "escalated": record.escalated,
                "verification_passed": record.verification_passed,
                "retry_count": record.retry_count,
            },
            "inputs": {"task": record.task_input},
            "outputs": {"result": record.task_output},
            "timeline": {
                "start_time": record.start_time,
                "end_time": record.end_time,
            },
            "anomalies": record.anomalies,
            "metrics": record.metrics,
        }
        return json.dumps(report, indent=2)

    async def run(self, task: str) -> str:
        """Execute the assigned task with full lifecycle management.

        This method handles task validation, execution with retry logic,
        observability logging, escalation evaluation, and completion reporting.

        Args:
            task: The task description to execute.

        Returns:
            Completion report as a JSON string documenting the full task execution.
        """
        record = TaskRecord(task_input=task)
        start_time = time.time()

        self.obs_logger.emit("task_received", record.task_id, {"task": task})

        is_valid, validation_message = self._validate_task(task)
        if not is_valid:
            record.status = "failed"
            record.anomalies.append(f"Validation failed: {validation_message}")
            record.end_time = datetime.now(timezone.utc).isoformat()
            record.metrics["duration_seconds"] = time.time() - start_time
            self.obs_logger.emit(
                "task_validation_failed",
                record.task_id,
                {"reason": validation_message},
            )
            self._save_task_record(record)
            self._update_registry(record)
            return self._generate_completion_report(record)

        self.obs_logger.emit("task_validated", record.task_id, {"message": validation_message})
        record.status = "running"
        self._update_registry(record)

        system_prompt = f"""You are {self.agent_name}, an AI agent for the {self.department} department.

Your mission: Test mission for automated testing. This agent supports the general department in executing its core responsibilities. It operates with precision and reliability to fulfill its designated objectives.

Your responsibilities:
- Receive, validate, and execute assigned tasks within the general department scope using approved tools
- Maintain accurate and up-to-date task state records in the registry and filesystem
- Apply defined decision rules consistently across all task executions without deviation
- Emit structured observability logs and metrics for every task lifecycle event
- Evaluate and enforce escalation triggers at the conclusion of each task or upon detecting failure conditions
- Produce completion reports that document inputs, outputs, verification results, and any anomalies encountered
- Adhere strictly to retry policy parameters during transient failure recovery
- Support audit and compliance requirements by preserving immutable task outcome records

You have access to filesystem_server and registry_server tools. Use them to maintain task state and records.
Always be precise, reliable, and thorough in your task execution.
Current task ID: {record.task_id}"""

        messages = [{"role": "user", "content": task}]
        last_error = None

        for attempt in range(self.max_retries):
            if attempt > 0:
                record.retry_count = attempt
                self.obs_logger.emit(
                    "task_retry",
                    record.task_id,
                    {"attempt": attempt, "max_retries": self.max_retries},
                )
                await asyncio.sleep(self.retry_delay * attempt)

            try:
                self.obs_logger.emit(
                    "llm_call_started",
                    record.task_id,
                    {"attempt": attempt + 1, "model": self.model},
                )

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    tools=self.tools,
                    messages=messages,
                )

                self.obs_logger.emit(
                    "llm_call_completed",
                    record.task_id,
                    {
                        "stop_reason": response.stop_reason,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                )

                record.metrics["total_input_tokens"] = (
                    record.metrics.get("total_input_tokens", 0) + response.usage.input_tokens
                )
                record.metrics["total_output_tokens"] = (
                    record.metrics.get("total_output_tokens", 0) + response.usage.output_tokens
                )

                while response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            self.obs_logger.emit(
                                "tool_call_started",
                                record.task_id,
                                {"tool": block.name, "input": block.input},
                            )
                            try:
                                tool_result = self._process_tool_call(block.name, block.input)
                                self.obs_logger.emit(
                                    "tool_call_completed",
                                    record.task_id,
                                    {"tool": block.name, "result_length": len(tool_result)},
                                )
                            except Exception as tool_error:
                                tool_result = f"Tool error: {str(tool_error)}"
                                record.anomalies.append(
                                    f"Tool {block.name} error: {str(tool_error)}"
                                )
                                self.obs_logger.emit(
                                    "tool_call_failed",
                                    record.task_id,
                                    {"tool": block.name, "error": str(tool_error)},
                                )

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": tool_result,
                                }
                            )

                    messages = messages + [
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results},
                    ]

                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=system_prompt,
                        tools=self.tools,
                        messages=messages,
                    )

                    self.obs_logger.emit(
                        "llm_call_completed",
                        record.task_id,
                        {
                            "stop_reason": response.stop_reason,
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                        },
                    )

                    record.metrics["total_input_tokens"] = (
                        record.metrics.get("total_input_tokens", 0)
                        + response.usage.input_tokens
                    )
                    record.metrics["total_output_tokens"] = (
                        record.metrics.get("total_output_tokens", 0)
                        + response.usage.output_tokens
                    )

                final_output = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_output += block.text

                record.task_output = final_output
                record.status = "completed"
                record.verification_passed = True
                last_error = None
                break

            except anthropic.RateLimitError as e:
                last_error = str(e)
                record.anomalies.append(f"Rate limit error on attempt {attempt + 1}: {last_error}")
                self.obs_logger.emit(
                    "rate_limit_error",
                    record.task_id,
                    {"attempt": attempt + 1, "error": last_error},
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 2) * 2)

            except anthropic.APIConnectionError as e:
                last_error = str(e)
                record.anomalies.append(
                    f"Connection error on attempt {attempt + 1}: {last_error}"
                )
                self.obs_logger.emit(
                    "connection_error",
                    record.task_id,
                    {"attempt": attempt + 1, "error": last_error},
                )

            except anthropic.APIStatusError as e:
                last_error = str(e)
                record.anomalies.append(f"API error on attempt {attempt + 1}: {last_error}")
                self.obs_logger.emit(
                    "api_error",
                    record.task_id,
                    {"attempt": attempt + 1, "status_code": e.status_code, "error": last_error},
                )
                if e.status_code < 500:
                    break

            except Exception as e:
                last_error = str(e)
                record.anomalies.append(
                    f"Unexpected error on attempt {attempt + 1}: {last_error}"
                )
                self.obs_logger.emit(
                    "unexpected_error",
                    record.task_id,
                    {"attempt": attempt + 1, "error": last_error},
                )

        if last_error is not None:
            record.status = "failed"
            record.verification_passed = False
            self.obs_logger.emit(
                "task_failed",
                record.task_id,
                {"error": last_error, "total_retries": record.retry_count},
            )

        record.escalated = self._should_escalate(record)
        if record.escalated:
            self.obs_logger.emit(
                "task_escalated",
                record.task_id,
                {
                    "reason": "Escalation threshold reached or failure with anomalies",
                    "retry_count": record.retry_count,
                    "anomaly_count": len(record.anomalies),
                },
            )

        record.end_time = datetime.now(timezone.utc).isoformat()
        record.metrics["duration_seconds"] = time.time() - start_time
        record.metrics["total_retries"] = record.retry_count

        self._save_task_record(record)
        self._update_registry(record)

        completion_report = self._generate_completion_report(record)

        self.obs_logger.emit(
            "task_completed",
            record.task_id,
            {
                "status": record.status,
                "escalated": record.escalated,
                "verification_passed": record.verification_passed,
                "duration_seconds": record.metrics["duration_seconds"],
            },
        )

        return completion_report


async def main():
    """Main entry point for running the agent."""
    agent = TestAgentA31Eea32()
    task = os.getenv(
        "AGENT_TASK",
        "Perform a system health check and report the current status of all monitored components.",
    )
    result = await agent.run(task)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())