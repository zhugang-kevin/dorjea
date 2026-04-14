"""
exists_agent_d821178e.py

Production agent for the 'general' department.
Mission: Test mission. This agent supports the general department in achieving its objectives.
         It operates with precision and efficiency to fulfill assigned tasks.
"""

import os
import json
import asyncio
import logging
import datetime
from typing import Any

import anthropic
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("exists_agent_d821178e")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class TaskRecord(BaseModel):
    """Represents a single task execution record stored in the registry."""

    task_id: str = Field(..., description="Unique identifier for the task")
    task_description: str = Field(..., description="Original task string")
    status: str = Field(..., description="pending | running | completed | failed | escalated")
    started_at: str = Field(..., description="ISO-8601 timestamp when execution began")
    completed_at: str | None = Field(None, description="ISO-8601 timestamp when execution ended")
    result: str | None = Field(None, description="Final result or error message")
    anomalies: list[str] = Field(default_factory=list, description="Any anomalies detected")


class AgentConfig(BaseModel):
    """Runtime configuration loaded from environment variables."""

    api_key: str
    model: str
    department: str
    registry_path: str
    assets_path: str
    max_tokens: int
    max_iterations: int
    escalation_threshold: int


# ---------------------------------------------------------------------------
# Tool definitions (MCP-style tool schemas for the Anthropic API)
# ---------------------------------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {
        "name": "filesystem_read",
        "description": (
            "Read a file from the departmental filesystem. "
            "Returns the file contents as a string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path (under the assets directory) of the file to read.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "filesystem_write",
        "description": (
            "Write content to a file in the departmental filesystem. "
            "Creates the file if it does not exist; overwrites otherwise."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path (under the assets directory) of the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "registry_read",
        "description": (
            "Read a record from the task registry by task_id. "
            "Returns the JSON-serialised TaskRecord or an error message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The unique task identifier to look up.",
                }
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "registry_write",
        "description": (
            "Persist a TaskRecord to the registry. "
            "Creates or updates the record identified by task_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The unique task identifier.",
                },
                "record": {
                    "type": "object",
                    "description": "The TaskRecord fields as a JSON object.",
                },
            },
            "required": ["task_id", "record"],
        },
    },
    {
        "name": "registry_list",
        "description": "List all task IDs currently stored in the registry.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------
class ExistsAgentD821178E:
    """
    Production agent for the 'general' department.

    Responsibilities:
    - Parse, validate, and execute task specifications assigned to the general department
    - Maintain accurate and timestamped records of all task executions in the registry
    - Read and write departmental assets to the filesystem in accordance with task requirements
    - Monitor task execution state and detect deviations from the planned workflow
    - Apply quality validation checks to all outputs before marking tasks complete
    - Document all decisions, actions, and anomalies encountered during task execution
    - Escalate tasks that exceed defined thresholds or fall outside agent capabilities
    - Operate strictly within the boundaries defined by allowed tools and non-responsibilities

    Allowed tools: filesystem_server, registry_server
    Model: claude-sonnet-4-6
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        """
        Initialise the agent by reading all configuration from environment variables.

        Required environment variables
        --------------------------------
        ANTHROPIC_API_KEY          : Anthropic API key
        AGENT_MODEL                : Model identifier (default: claude-sonnet-4-6)
        AGENT_DEPARTMENT           : Department name (default: general)
        AGENT_REGISTRY_PATH        : Filesystem path for the JSON registry file
        AGENT_ASSETS_PATH          : Root directory for departmental file assets
        AGENT_MAX_TOKENS           : Maximum tokens per LLM response (default: 4096)
        AGENT_MAX_ITERATIONS       : Agentic loop iteration cap (default: 20)
        AGENT_ESCALATION_THRESHOLD : Iteration count that triggers escalation (default: 15)
        """
        self.config = AgentConfig(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
            department=os.getenv("AGENT_DEPARTMENT", "general"),
            registry_path=os.getenv("AGENT_REGISTRY_PATH", "/tmp/agent_registry.json"),
            assets_path=os.getenv("AGENT_ASSETS_PATH", "/tmp/agent_assets"),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "4096")),
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "20")),
            escalation_threshold=int(os.getenv("AGENT_ESCALATION_THRESHOLD", "15")),
        )

        if not self.config.api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")

        self.client = anthropic.Anthropic(api_key=self.config.api_key)

        # Ensure required directories / files exist
        self._bootstrap_filesystem()

        logger.info(
            "ExistsAgentD821178E initialised | department=%s | model=%s",
            self.config.department,
            self.config.model,
        )

    # ------------------------------------------------------------------
    # Bootstrap helpers
    # ------------------------------------------------------------------
    def _bootstrap_filesystem(self) -> None:
        """
        Create the assets directory and registry file if they do not already exist.
        Logs but does not raise on failure so the agent can still attempt to run.
        """
        try:
            os.makedirs(self.config.assets_path, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create assets directory: %s", exc)

        try:
            if not os.path.exists(self.config.registry_path):
                with open(self.config.registry_path, "w", encoding="utf-8") as fh:
                    json.dump({}, fh)
        except OSError as exc:
            logger.warning("Could not initialise registry file: %s", exc)

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------
    def _registry_load(self) -> dict[str, Any]:
        """
        Load the entire registry from disk.

        Returns
        -------
        dict
            Mapping of task_id -> raw record dict.  Empty dict on error.
        """
        try:
            with open(self.config.registry_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load registry: %s", exc)
            return {}

    def _registry_save(self, data: dict[str, Any]) -> bool:
        """
        Persist the registry dict to disk atomically (write-then-rename).

        Parameters
        ----------
        data : dict
            Full registry mapping to persist.

        Returns
        -------
        bool
            True on success, False on failure.
        """
        tmp_path = self.config.registry_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp_path, self.config.registry_path)
            return True
        except OSError as exc:
            logger.error("Failed to save registry: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------
    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Dispatch a tool call and return its string result.

        Parameters
        ----------
        tool_name  : str  Name of the tool to invoke.
        tool_input : dict Parameters for the tool.

        Returns
        -------
        str
            JSON-encoded result or a plain error string.
        """
        try:
            if tool_name == "filesystem_read":
                return self._tool_filesystem_read(tool_input)
            elif tool_name == "filesystem_write":
                return self._tool_filesystem_write(tool_input)
            elif tool_name == "registry_read":
                return self._tool_registry_read(tool_input)
            elif tool_name == "registry_write":
                return self._tool_registry_write(tool_input)
            elif tool_name == "registry_list":
                return self._tool_registry_list()
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error in tool '%s': %s", tool_name, exc)
            return json.dumps({"error": str(exc)})

    def _tool_filesystem_read(self, params: dict[str, Any]) -> str:
        """
        Read a file from the assets directory.

        Parameters
        ----------
        params : dict  Must contain 'path' key.

        Returns
        -------
        str  File contents or JSON error.
        """
        relative_path: str = params.get("path", "")
        if not relative_path:
            return json.dumps({"error": "path parameter is required"})

        # Prevent path traversal
        full_path = os.path.realpath(os.path.join(self.config.assets_path, relative_path))
        assets_root = os.path.realpath(self.config.assets_path)
        if not full_path.startswith(assets_root):
            return json.dumps({"error": "Path traversal detected; access denied."})

        try:
            with open(full_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            return json.dumps({"path": relative_path, "content": content})
        except FileNotFoundError:
            return json.dumps({"error": f"File not found: {relative_path}"})
        except OSError as exc:
            return json.dumps({"error": str(exc)})

    def _tool_filesystem_write(self, params: dict[str, Any]) -> str:
        """
        Write content to a file in the assets directory.

        Parameters
        ----------
        params : dict  Must contain 'path' and 'content' keys.

        Returns
        -------
        str  JSON success/error message.
        """
        relative_path: str = params.get("path", "")
        content: str = params.get("content", "")
        if not relative_path:
            return json.dumps({"error": "path parameter is required"})

        full_path = os.path.realpath(os.path.join(self.config.assets_path, relative_path))
        assets_root = os.path.realpath(self.config.assets_path)
        if not full_path.startswith(assets_root):
            return json.dumps({"error": "Path traversal detected; access denied."})

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            return json.dumps({"status": "ok", "path": relative_path, "bytes_written": len(content)})
        except OSError as exc:
            return json.dumps({"error": str(exc)})

    def _tool_registry_read(self, params: dict[str, Any]) -> str:
        """
        Read a single task record from the registry.

        Parameters
        ----------
        params : dict  Must contain 'task_id' key.

        Returns
        -------
        str  JSON-encoded TaskRecord or error.
        """
        task_id: str = params.get("task_id", "")
        if not task_id:
            return json.dumps({"error": "task_id parameter is required"})

        registry = self._registry_load()
        record = registry.get(task_id)
        if record is None:
            return json.dumps({"error": f"No record found for task_id: {task_id}"})
        return json.dumps(record)

    def _tool_registry_write(self, params: dict[str, Any]) -> str:
        """
        Write or update a task record in the registry.

        Parameters
        ----------
        params : dict  Must contain 'task_id' and 'record' keys.

        Returns
        -------
        str  JSON success/error message.
        """
        task_id: str = params.get("task_id", "")
        record: dict[str, Any] = params.get("record", {})
        if not task_id:
            return json.dumps({"error": "task_id parameter is required"})
        if not isinstance(record, dict):
            return json.dumps({"error": "record must be a JSON object"})

        registry = self._registry_load()
        registry[task_id] = record
        success = self._registry_save(registry)
        if success:
            return json.dumps({"status": "ok", "task_id": task_id})
        return json.dumps({"error": "Failed to persist registry"})

    def _tool_registry_list(self) -> str:
        """
        List all task IDs in the registry.

        Returns
        -------
        str  JSON array of task_id strings.
        """
        registry = self._registry_load()
        return json.dumps({"task_ids": list(registry.keys())})

    # ------------------------------------------------------------------
    # Quality validation
    # ------------------------------------------------------------------
    def _validate_output(self, result: str) -> tuple[bool, list[str]]:
        """
        Apply quality validation checks to a task result before marking it complete.

        Parameters
        ----------
        result : str  The final result string produced by the agent.

        Returns
        -------
        tuple[bool, list[str]]
            (is_valid, list_of_anomalies)
        """
        anomalies: list[str] = []

        if not result or not result.strip():
            anomalies.append("Result is empty or whitespace-only.")

        if len(result) > 100_000:
            anomalies.append("Result exceeds 100 000 character safety limit.")

        forbidden_patterns = ["<script", "DROP TABLE", "rm -rf"]
        for pattern in forbidden_patterns:
            if pattern.lower() in result.lower():
                anomalies.append(f"Potentially unsafe content detected: '{pattern}'")

        return len(anomalies) == 0, anomalies

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------
    def _build_system_prompt(self) -> str:
        """
        Construct the system prompt that governs the agent's behaviour.

        Returns
        -------
        str  Fully-formed system prompt string.
        """
        return (
            f"You are exists_agent_d821178e, a production AI agent operating in the "
            f"'{self.config.department}' department.\n\n"
            "MISSION:\n"
            "Test mission. This agent supports the general department in achieving its objectives. "
            "It operates with precision and efficiency to fulfill assigned tasks.\n\n"
            "RESPONSIBILITIES:\n"
            "1. Parse, validate, and execute task specifications assigned to the general department.\n"
            "2. Maintain accurate and timestamped records of all task executions in the registry.\n"
            "3. Read and write departmental assets to the filesystem in accordance with task requirements.\n"
            "4. Monitor task execution state and detect deviations from the planned workflow.\n"
            "5. Apply quality validation checks to all outputs before marking tasks complete.\n"
            "6. Document all decisions, actions, and anomalies encountered during task execution.\n"
            "7. Escalate tasks that exceed defined thresholds or fall outside agent capabilities.\n"
            "8. Operate strictly within the boundaries defined by allowed tools and non-responsibilities.\n\n"
            "ALLOWED TOOLS: filesystem_server (filesystem_read, filesystem_write), "
            "registry_server (registry_read, registry_write, registry_list).\n\n"
            "OPERATING RULES:\n"
            "- Always record task start and completion in the registry.\n"
            "- Never fabricate file contents; only report what tools return.\n"
            "- If a task is ambiguous, document the ambiguity and make a reasonable, safe assumption.\n"
            "- If you cannot complete a task within your capabilities, escalate with a clear explanation.\n"
            "- Produce a concise, factual final answer summarising what was accomplished.\n"
        )

    # ------------------------------------------------------------------
    # Core agentic loop
    # ------------------------------------------------------------------
    async def run(self, task: str) -> str:
        """
        Execute a task using an agentic loop with tool use.

        The method:
        1. Creates a timestamped TaskRecord and persists it to the registry.
        2. Runs an iterative LLM loop, dispatching tool calls as requested.
        3. Detects escalation conditions (iteration threshold exceeded).
        4. Validates the final output before marking the task complete.
        5. Updates the registry record with the final status and result.

        Parameters
        ----------
        task : str  Natural-language task description to execute.

        Returns
        -------
        str
            The final result string, or an escalation/error message.
        """
        task_id = f"task_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        started_at = datetime.datetime.utcnow().isoformat() + "Z"
        anomalies: list[str] = []

        # Initialise registry record
        record = TaskRecord(
            task_id=task_id,
            task_description=task,
            status="running",
            started_at=started_at,
        )
        self._persist_record(record)

        logger.info("Task started | task_id=%s", task_id)

        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        final_result: str = ""
        iteration = 0

        try:
            while iteration < self.config.max_iterations:
                iteration += 1
                logger.debug("Iteration %d/%d", iteration, self.config.max_iterations)

                # Escalation threshold check
                if iteration >= self.config.escalation_threshold:
                    escalation_msg = (
                        f"Task escalated after {iteration} iterations without resolution. "
                        f"task_id={task_id}. Manual review required."
                    )
                    logger.warning(escalation_msg)
                    anomalies.append(escalation_msg)
                    record.status = "escalated"
                    record.result = escalation_msg
                    record.anomalies = anomalies
                    record.completed_at = datetime.datetime.utcnow().isoformat() + "Z"
                    self._persist_record(record)
                    return escalation_msg

                # Call the LLM
                try:
                    response = self.client.messages.create(
                        model=self.config.model,
                        max_tokens=self.config.max_tokens,
                        system=self._build_system_prompt(),
                        tools=TOOLS,  # type: ignore[arg-type]
                        messages=messages,
                    )
                except anthropic.APIConnectionError as exc:
                    err = f"API connection error on iteration {iteration}: {exc}"
                    logger.error(err)
                    anomalies.append(err)
                    break
                except anthropic.RateLimitError as exc:
                    err = f"Rate limit hit on iteration {iteration}: {exc}"
                    logger.error(err)
                    anomalies.append(err)
                    await asyncio.sleep(5)
                    continue
                except anthropic.APIStatusError as exc:
                    err = f"API status error {exc.status_code} on iteration {iteration}: {exc.message}"
                    logger.error(err)
                    anomalies.append(err)
                    break

                # Process stop reason
                stop_reason = response.stop_reason

                if stop_reason == "end_turn":
                    # Extract the final text response
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_result = block.text
                            break
                    logger.info("Agent reached end_turn | task_id=%s", task_id)
                    break

                if stop_reason == "tool_use":
                    # Append assistant message
                    messages.append({"role": "assistant", "content": response.content})

                    # Execute each tool call
                    tool_results: list[dict[str, Any]] = []
                    for block in response.content:
                        if block.type == "tool_use":
                            logger.info(
                                "Tool call: %s | input=%s", block.name, block.input
                            )
                            tool_output = self._execute_tool(block.name, block.input)
                            logger.debug("Tool result: %s", tool_output[:200])
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": tool_output,
                                }
                            )

                    messages.append({"role": "user", "content": tool_results})
                    continue

                # Unexpected stop reason
                anomaly = f"Unexpected stop_reason '{stop_reason}' on iteration {iteration}."
                logger.warning(anomaly)
                anomalies.append(anomaly)
                break

        except Exception as exc:  # pylint: disable=broad-except
            err = f"Unhandled exception during task execution: {exc}"
            logger.exception(err)
            anomalies.append(err)
            record.status = "failed"
            record.result = err
            record.anomalies = anomalies
            record.completed_at = datetime.datetime.utcnow().isoformat() + "Z"
            self._persist_record(record)
            return err

        # Quality validation
        is_valid, validation_anomalies = self._validate_output(final_result)
        anomalies.extend(validation_anomalies)
        if not is_valid:
            logger.warning("Output validation failed | anomalies=%s", validation_anomalies)

        # Finalise record
        record.status = "completed" if is_valid else "failed"
        record.result = final_result
        record.anomalies = anomalies
        record.completed_at = datetime.datetime.utcnow().isoformat() + "Z"
        self._persist_record(record)

        logger.info(
            "Task finished | task_id=%s | status=%s | iterations=%d",
            task_id,
            record.status,
            iteration,
        )
        return final_result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _persist_record(self, record: TaskRecord) -> None:
        """
        Serialise and write a TaskRecord to the registry.

        Parameters
        ----------
        record : TaskRecord  The record to persist.
        """
        try:
            registry = self._registry_load()
            registry[record.task_id] = record.model_dump()
            self._registry_save(registry)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to persist task record %s: %s", record.task_id, exc)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
async def _main() -> None:
    """Run a quick smoke-test when the module is executed directly."""
    agent = ExistsAgentD821178E()
    sample_task = (
        "List all files currently tracked in the registry and write a summary "
        "report to 'reports/summary.txt' in the assets directory."
    )
    result = await agent.run(sample_task)
    print("=== Agent Result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(_main())