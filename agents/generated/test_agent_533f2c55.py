"""
test_agent_533f2c55.py

Production agent module for test_agent_533f2c55.
Mission: Test mission for automated testing. This agent supports the general department
in executing its core responsibilities. It operates with precision and reliability
to fulfill its designated objectives.
"""

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


# ---------------------------------------------------------------------------
# Observability / structured logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_agent_533f2c55")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TaskState(BaseModel):
    """Represents the persisted state of a running or completed task."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = "test_agent_533f2c55"
    department: str = "general"
    status: str = "pending"  # pending | running | completed | failed | escalated
    task_input: str = ""
    result: str = ""
    error: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metrics: dict[str, Any] = Field(default_factory=dict)
    escalation_context: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Runtime configuration loaded from environment variables."""

    api_key: str
    model: str
    max_tokens: int
    temperature: float
    department: str
    registry_path: str
    filesystem_base_path: str
    escalation_threshold: int
    agent_version: str


class ResultReport(BaseModel):
    """Schema-valid result report emitted at the end of every task."""

    task_id: str
    agent_name: str = "test_agent_533f2c55"
    department: str = "general"
    status: str
    task_input: str
    result: str
    error: str
    duration_seconds: float
    metrics: dict[str, Any]
    escalated: bool
    report_generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Tool definitions (MCP-style tool schemas for the Anthropic client)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "filesystem_server",
        "description": (
            "Read from or write to the local filesystem. "
            "Supports actions: 'read', 'write', 'list', 'delete'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete"],
                    "description": "The filesystem operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file/directory path.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (required for 'write' action).",
                },
            },
            "required": ["action", "path"],
        },
    },
    {
        "name": "registry_server",
        "description": (
            "Interact with the agent registry for configuration and state persistence. "
            "Supports actions: 'get', 'set', 'delete', 'list'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set", "delete", "list"],
                    "description": "The registry operation to perform.",
                },
                "key": {
                    "type": "string",
                    "description": "Registry key (required for get/set/delete).",
                },
                "value": {
                    "type": "string",
                    "description": "Value to store (required for 'set' action).",
                },
                "namespace": {
                    "type": "string",
                    "description": "Optional namespace prefix for the key.",
                },
            },
            "required": ["action"],
        },
    },
]


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class TestAgent533F2C55:
    """
    Production agent for the general department.

    Mission: Test mission for automated testing. This agent supports the general
    department in executing its core responsibilities. It operates with precision
    and reliability to fulfill its designated objectives.

    Responsibilities:
        - Execute assigned test tasks for the general department with full fidelity
          to the defined execution workflow.
        - Validate all input parameters and artifacts before beginning core task
          processing.
        - Persist intermediate and final task state to registry and filesystem as
          specified in the memory interface.
        - Apply all defined decision rules at appropriate workflow branch points
          without omission.
        - Emit structured observability events and logs at every tracked metric
          point throughout execution.
        - Detect and respond to all escalation triggers promptly, packaging full
          context for the receiving supervisor.
        - Maintain version and configuration integrity by reading from registry at
          initialization and never assuming stale cached values.
        - Produce complete, schema-valid result reports for every task regardless
          of pass or fail outcome.
    """

    AGENT_NAME = "test_agent_533f2c55"
    DEPARTMENT = "general"

    # In-memory registry simulation (keyed by namespace:key)
    _registry_store: dict[str, str] = {}

    def __init__(self) -> None:
        """
        Initialize the agent by reading all configuration from environment variables.

        Environment variables consumed:
            ANTHROPIC_API_KEY        – Anthropic API key (required).
            AGENT_MODEL              – Model identifier (default: claude-sonnet-4-6).
            AGENT_MAX_TOKENS         – Max tokens per LLM call (default: 4096).
            AGENT_TEMPERATURE        – Sampling temperature (default: 0.2).
            AGENT_DEPARTMENT         – Department name (default: general).
            AGENT_REGISTRY_PATH      – Path for registry persistence (default: /tmp/registry).
            AGENT_FILESYSTEM_BASE    – Base path for filesystem ops (default: /tmp/agent_fs).
            AGENT_ESCALATION_THRESHOLD – Retry count before escalation (default: 3).
            AGENT_VERSION            – Agent version string (default: 1.0.0).

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required.")

        self.config = AgentConfig(
            api_key=api_key,
            model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.2")),
            department=os.getenv("AGENT_DEPARTMENT", "general"),
            registry_path=os.getenv("AGENT_REGISTRY_PATH", "/tmp/registry"),
            filesystem_base_path=os.getenv("AGENT_FILESYSTEM_BASE", "/tmp/agent_fs"),
            escalation_threshold=int(os.getenv("AGENT_ESCALATION_THRESHOLD", "3")),
            agent_version=os.getenv("AGENT_VERSION", "1.0.0"),
        )

        self._client = anthropic.Anthropic(api_key=self.config.api_key)
        self._ensure_directories()
        self._emit_event("agent_initialized", {"version": self.config.agent_version})
        logger.info(
            "Agent %s v%s initialized for department '%s'.",
            self.AGENT_NAME,
            self.config.agent_version,
            self.config.department,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, task: str) -> str:
        """
        Execute a task end-to-end and return a JSON-serialized ResultReport.

        Workflow:
            1. Validate input.
            2. Load fresh config from registry.
            3. Persist initial task state.
            4. Run the agentic LLM loop with tool use.
            5. Apply decision rules at branch points.
            6. Detect escalation triggers and handle if needed.
            7. Persist final state.
            8. Produce and return a schema-valid ResultReport.

        Args:
            task: Natural-language task description to execute.

        Returns:
            JSON string conforming to the ResultReport schema.
        """
        start_time = time.monotonic()
        state = TaskState(task_input=task, department=self.config.department)
        self._emit_event("task_started", {"task_id": state.task_id, "task": task})

        try:
            # Step 1 – Validate input
            self._validate_input(task, state)

            # Step 2 – Refresh config from registry
            self._refresh_config_from_registry(state)

            # Step 3 – Persist initial state
            self._persist_state(state, phase="initial")

            # Step 4 – Agentic loop
            result = await self._agentic_loop(task, state)
            state.result = result
            state.status = "completed"

        except EscalationError as exc:
            state.status = "escalated"
            state.error = str(exc)
            state.escalation_context = exc.context
            self._handle_escalation(state)
        except ValidationError as exc:
            state.status = "failed"
            state.error = f"Validation error: {exc}"
            self._emit_event("task_validation_failed", {"task_id": state.task_id, "error": state.error})
        except Exception as exc:  # noqa: BLE001
            state.status = "failed"
            state.error = f"Unexpected error: {exc}"
            logger.exception("Unhandled exception in task %s", state.task_id)
            self._emit_event("task_failed", {"task_id": state.task_id, "error": state.error})
        finally:
            state.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist_state(state, phase="final")

        duration = time.monotonic() - start_time
        state.metrics["duration_seconds"] = round(duration, 4)

        report = self._build_report(state, duration)
        self._emit_event("task_completed", {"task_id": state.task_id, "status": state.status})
        return report.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_input(self, task: str, state: TaskState) -> None:
        """
        Validate the task input before processing begins.

        Args:
            task: The raw task string provided by the caller.
            state: Current TaskState for metric tracking.

        Raises:
            ValidationError: If the task string is empty or exceeds limits.
        """
        self._emit_event("validation_started", {"task_id": state.task_id})
        if not task or not task.strip():
            raise ValidationError("Task input must not be empty.")
        if len(task) > 32_000:
            raise ValidationError(
                f"Task input length {len(task)} exceeds maximum of 32,000 characters."
            )
        state.metrics["input_length"] = len(task)
        self._emit_event("validation_passed", {"task_id": state.task_id})
        logger.info("Input validation passed for task %s.", state.task_id)

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------

    def _refresh_config_from_registry(self, state: TaskState) -> None:
        """
        Read agent version and configuration from the registry at runtime.

        This ensures stale cached values are never used. Any registry read
        failure is logged but does not abort execution.

        Args:
            state: Current TaskState for metric tracking.
        """
        self._emit_event("registry_config_refresh_started", {"task_id": state.task_id})
        try:
            version_key = f"{self.AGENT_NAME}:version"
            stored_version = self._registry_get(version_key)
            if stored_version:
                logger.info(
                    "Registry version for %s: %s (env: %s)",
                    self.AGENT_NAME,
                    stored_version,
                    self.config.agent_version,
                )
                state.metrics["registry_version"] = stored_version
            else:
                # Write current version into registry for future reads
                self._registry_set(version_key, self.config.agent_version)
                state.metrics["registry_version"] = self.config.agent_version
        except Exception as exc:  # noqa: BLE001
            logger.warning("Registry config refresh failed (non-fatal): %s", exc)
            self._emit_event(
                "registry_config_refresh_failed",
                {"task_id": state.task_id, "error": str(exc)},
            )
        self._emit_event("registry_config_refresh_done", {"task_id": state.task_id})

    def _registry_get(self, key: str, namespace: str = "") -> str:
        """
        Retrieve a value from the in-memory registry store.

        Args:
            key: Registry key to look up.
            namespace: Optional namespace prefix.

        Returns:
            The stored string value, or empty string if not found.
        """
        full_key = f"{namespace}:{key}" if namespace else key
        return self.__class__._registry_store.get(full_key, "")

    def _registry_set(self, key: str, value: str, namespace: str = "") -> None:
        """
        Store a value in the in-memory registry store.

        Args:
            key: Registry key.
            value: String value to store.
            namespace: Optional namespace prefix.
        """
        full_key = f"{namespace}:{key}" if namespace else key
        self.__class__._registry_store[full_key] = value

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _persist_state(self, state: TaskState, phase: str) -> None:
        """
        Persist the current TaskState to both the registry and the filesystem.

        Args:
            state: The TaskState to persist.
            phase: Lifecycle phase label ('initial', 'intermediate', 'final').
        """
        self._emit_event(
            "state_persist_started",
            {"task_id": state.task_id, "phase": phase, "status": state.status},
        )
        state.updated_at = datetime.now(timezone.utc).isoformat()
        payload = state.model_dump_json()

        # Registry persistence
        try:
            registry_key = f"{self.AGENT_NAME}:tasks:{state.task_id}"
            self._registry_set(registry_key, payload)
            logger.debug("State persisted to registry for task %s (%s).", state.task_id, phase)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Registry state persistence failed: %s", exc)

        # Filesystem persistence
        try:
            task_dir = os.path.join(
                self.config.filesystem_base_path, "tasks", state.task_id
            )
            os.makedirs(task_dir, exist_ok=True)
            state_file = os.path.join(task_dir, f"state_{phase}.json")
            with open(state_file, "w", encoding="utf-8") as fh:
                fh.write(payload)
            logger.debug("State persisted to filesystem: %s", state_file)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Filesystem state persistence failed: %s", exc)

        self._emit_event(
            "state_persist_done",
            {"task_id": state.task_id, "phase": phase},
        )

    # ------------------------------------------------------------------
    # Agentic loop
    # ------------------------------------------------------------------

    async def _agentic_loop(self, task: str, state: TaskState) -> str:
        """
        Run the multi-turn LLM agentic loop with tool use until completion.

        The loop continues until the model returns a stop_reason of 'end_turn'
        or the escalation threshold is exceeded.

        Args:
            task: The task description to pass to the model.
            state: Current TaskState for metric and escalation tracking.

        Returns:
            The final text result produced by the model.

        Raises:
            EscalationError: If the loop iteration count exceeds the threshold.
        """
        system_prompt = self._build_system_prompt()
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        iteration = 0
        final_text = ""

        self._emit_event("agentic_loop_started", {"task_id": state.task_id})

        while True:
            iteration += 1
            state.metrics["loop_iterations"] = iteration
            self._emit_event(
                "loop_iteration",
                {"task_id": state.task_id, "iteration": iteration},
            )

            # Escalation check
            if iteration > self.config.escalation_threshold:
                raise EscalationError(
                    f"Escalation threshold ({self.config.escalation_threshold}) exceeded "
                    f"after {iteration - 1} iterations.",
                    context={
                        "task_id": state.task_id,
                        "iteration": iteration,
                        "last_messages": messages[-4:],
                    },
                )

            # LLM call
            try:
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt,
                    tools=TOOLS,  # type: ignore[arg-type]
                    messages=messages,
                )
            except anthropic.APIConnectionError as exc:
                raise EscalationError(
                    f"API connection error: {exc}",
                    context={"task_id": state.task_id, "iteration": iteration},
                ) from exc
            except anthropic.RateLimitError as exc:
                raise EscalationError(
                    f"Rate limit exceeded: {exc}",
                    context={"task_id": state.task_id, "iteration": iteration},
                ) from exc
            except anthropic.APIStatusError as exc:
                raise EscalationError(
                    f"API status error {exc.status_code}: {exc.message}",
                    context={"task_id": state.task_id, "iteration": iteration},
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise EscalationError(
                    f"Unexpected LLM error: {exc}",
                    context={"task_id": state.task_id, "iteration": iteration},
                ) from exc

            state.metrics["total_input_tokens"] = (
                state.metrics.get("total_input_tokens", 0) + response.usage.input_tokens
            )
            state.metrics["total_output_tokens"] = (
                state.metrics.get("total_output_tokens", 0) + response.usage.output_tokens
            )

            # Collect assistant message content
            assistant_content: list[dict[str, Any]] = []
            tool_calls: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    final_text = block.text
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            messages.append({"role": "assistant", "content": assistant_content})

            # Decision rule: if no tool calls and stop reason is end_turn, we're done
            if response.stop_reason == "end_turn" and not tool_calls:
                self._emit_event(
                    "agentic_loop_completed",
                    {"task_id": state.task_id, "iterations": iteration},
                )
                break

            # Process tool calls
            if tool_calls:
                tool_results = self._process_tool_calls(tool_calls, state)
                messages.append({"role": "user", "content": tool_results})
                # Persist intermediate state after each tool round-trip
                self._persist_state(state, phase="intermediate")

        return final_text

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _process_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        state: TaskState,
    ) -> list[dict[str, Any]]:
        """
        Execute each tool call and return a list of tool_result content blocks.

        Args:
            tool_calls: List of tool call dicts with id, name, and input.
            state: Current TaskState for metric tracking.

        Returns:
            List of tool_result content blocks to append to the message history.
        """
        results: list[dict[str, Any]] = []
        for call in tool_calls:
            tool_name = call["name"]
            tool_input = call["input"]
            call_id = call["id"]

            self._emit_event(
                "tool_call_started",
                {"task_id": state.task_id, "tool": tool_name, "input": tool_input},
            )
            state.metrics[f"tool_calls_{tool_name}"] = (
                state.metrics.get(f"tool_calls_{tool_name}", 0) + 1
            )

            try:
                if tool_name == "filesystem_server":
                    output = self._execute_filesystem_tool(tool_input)
                elif tool_name == "registry_server":
                    output = self._execute_registry_tool(tool_input)
                else:
                    output = f"Unknown tool: {tool_name}"

                self._emit_event(
                    "tool_call_succeeded",
                    {"task_id": state.task_id, "tool": tool_name},
                )
            except Exception as exc:  # noqa: BLE001
                output = f"Tool error ({tool_name}): {exc}"
                logger.warning("Tool call failed for %s: %s", tool_name, exc)
                self._emit_event(
                    "tool_call_failed",
                    {"task_id": state.task_id, "tool": tool_name, "error": str(exc)},
                )

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": output,
                }
            )
        return results

    def _execute_filesystem_tool(self, tool_input: dict[str, Any]) -> str:
        """
        Execute a filesystem_server tool call.

        Supported actions: read, write, list, delete.

        Args:
            tool_input: Dict containing 'action', 'path', and optionally 'content'.

        Returns:
            String result of the filesystem operation.

        Raises:
            ValueError: If required parameters are missing or action is unknown.
            OSError: If the underlying filesystem operation fails.
        """
        action = tool_input.get("action", "")
        path = tool_input.get("path", "")
        if not path:
            raise ValueError("'path' is required for filesystem_server.")

        # Resolve path relative to base if not absolute
        if not os.path.isabs(path):
            path = os.path.join(self.config.filesystem_base_path, path)

        if action == "read":
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()

        elif action == "write":
            content = tool_input.get("content", "")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            return f"Written {len(content)} bytes to {path}."

        elif action == "list":
            if os.path.isdir(path):
                entries = os.listdir(path)
                return json.dumps(entries)
            raise ValueError(f"Path is not a directory: {path}")

        elif action == "delete":
            if os.path.isfile(path):
                os.remove(path)
                return f"Deleted file: {path}"
            raise ValueError(f"File not found for deletion: {path}")

        else:
            raise ValueError(f"Unknown filesystem action: {action}")

    def _execute_registry_tool(self, tool_input: dict[str, Any]) -> str:
        """
        Execute a registry_server tool call.

        Supported actions: get, set, delete, list.

        Args:
            tool_input: Dict containing 'action', optionally 'key', 'value', 'namespace'.

        Returns:
            String result of the registry operation.

        Raises:
            ValueError: If required parameters are missing or action is unknown.
        """
        action = tool_input.get("action", "")
        key = tool_input.get("key", "")
        value = tool_input.get("value", "")
        namespace = tool_input.get("namespace", "")

        if action == "get":
            if not key:
                raise ValueError("'key' is required for registry get.")
            result = self._registry_get(key, namespace)
            return result if result else "(not found)"

        elif action == "set":
            if not key:
                raise ValueError("'key' is required for registry set.")
            self._registry_set(key, value, namespace)
            return f"Registry key '{key}' set successfully."

        elif action == "delete":
            if not key:
                raise ValueError("'key' is required for registry delete.")
            full_key = f"{namespace}:{key}" if namespace else key
            removed = self.__class__._registry_store.pop(full_key, None)
            return f"Deleted key '{full_key}'." if removed is not None else f"Key '{full_key}' not found."

        elif action == "list":
            prefix = f"{namespace}:" if namespace else ""
            keys = [k for k in self.__class__._registry_store if k.startswith(prefix)]
            return json.dumps(keys)

        else:
            raise ValueError(f"Unknown registry action: {action}")

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def _handle_escalation(self, state: TaskState) -> None:
        """
        Package and persist full escalation context for the receiving supervisor.

        Args:
            state: The TaskState containing escalation_context and error details.
        """
        self._emit_event(
            "escalation_triggered",
            {
                "task_id": state.task_id,
                "error": state.error,
                "context": state.escalation_context,
            },
        )
        logger.warning(
            "Task %s escalated: %s",
            state.task_id,
            state.error,
        )

        # Persist escalation package to filesystem
        try:
            escalation_dir = os.path.join(
                self.config.filesystem_base_path, "escalations"
            )
            os.makedirs(escalation_dir, exist_ok=True)
            escalation_file = os.path.join(
                escalation_dir, f"{state.task_id}_escalation.json"
            )
            escalation_payload = {
                "task_id": state.task_id,
                "agent": self.AGENT_NAME,
                "department": self.DEPARTMENT,
                "error": state.error,
                "context": state.escalation_context,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(escalation_file, "w", encoding="utf-8") as fh:
                json.dump(escalation_payload, fh, indent=2)
            logger.info("Escalation package written to %s.", escalation_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to write escalation package: %s", exc)

        # Persist escalation key in registry
        try:
            self._registry_set(
                f"{self.AGENT_NAME}:escalations:{state.task_id}",
                json.dumps({"error": state.error, "timestamp": state.updated_at}),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist escalation to registry: %s", exc)

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _build_report(self, state: TaskState, duration: float) -> ResultReport:
        """
        Construct a schema-valid ResultReport from the final TaskState.

        Args:
            state: The completed (or failed/escalated) TaskState.
            duration: Wall-clock duration of the task in seconds.

        Returns:
            A fully populated ResultReport instance.
        """
        return ResultReport(
            task_id=state.task_id,
            department=state.department,
            status=state.status,
            task_input=state.task_input,
            result=state.result,
            error=state.error,
            duration_seconds=round(duration, 4),
            metrics=state.metrics,
            escalated=state.status == "escalated",
        )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """
        Emit a structured observability event to the logger.

        Args:
            event_name: Dot-separated event identifier.
            payload: Arbitrary key-value metadata for the event.
        """
        event = {
            "event": event_name,
            "agent": self.AGENT_NAME,
            "department": self.DEPARTMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        logger.info("OBSERVABILITY_EVENT %s", json.dumps(event))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """
        Construct the system prompt for the LLM.

        Returns:
            A fully formatted system prompt string.
        """
        return (
            f"You are {self.AGENT_NAME}, a production AI agent for the {self.DEPARTMENT} department.\n\n"
            "Mission: Test mission for automated testing. This agent supports the general department "
            "in executing its core responsibilities. It operates with precision and reliability to "
            "fulfill its designated objectives.\n\n"
            "Responsibilities:\n"
            "- Execute assigned test tasks for the general department with full fidelity to the "
            "defined execution workflow.\n"
            "- Validate all input parameters and artifacts before beginning core task processing.\n"
            "- Persist intermediate and final task state to registry and filesystem as specified "
            "in the memory interface.\n"
            "- Apply all defined decision rules at appropriate workflow branch points without omission.\n"
            "- Emit structured observability events and logs at every tracked metric point throughout "
            "execution.\n"
            "- Detect and respond to all escalation triggers promptly, packaging full context for "
            "the receiving supervisor.\n"
            "- Maintain version and configuration integrity by reading from registry at initialization "
            "