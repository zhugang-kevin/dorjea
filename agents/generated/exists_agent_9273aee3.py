"""
exists_agent_9273aee3.py

Production agent for the general department.
Mission: Test mission. This agent supports the general department with its core responsibilities.
It operates with precision and efficiency to fulfill its designated objectives.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("exists_agent_9273aee3")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TaskPayload(BaseModel):
    """Validated representation of an incoming task string."""

    raw: str = Field(..., description="Original task text")
    received_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp when the task was received",
    )


class CompletionReport(BaseModel):
    """Structured report emitted after every task execution."""

    agent: str = Field(default="exists_agent_9273aee3")
    department: str = Field(default="general")
    task_summary: str
    status: str  # "success" | "error" | "escalated"
    result: str
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error_detail: str | None = None


# ---------------------------------------------------------------------------
# Tool definitions (MCP-style tool specs passed to the model)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "filesystem_read",
        "description": "Read the contents of a file at the given path within authorized boundaries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path to read."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "filesystem_write",
        "description": "Write or overwrite a file at the given path with the provided content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write."},
                "content": {"type": "string", "description": "Content to write into the file."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "filesystem_update",
        "description": "Append or patch content in an existing file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to update."},
                "content": {"type": "string", "description": "Content to append."},
                "mode": {
                    "type": "string",
                    "enum": ["append", "prepend"],
                    "description": "Update mode.",
                },
            },
            "required": ["path", "content", "mode"],
        },
    },
    {
        "name": "filesystem_list",
        "description": "List files and directories under a given directory path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path to list."}
            },
            "required": ["directory"],
        },
    },
    {
        "name": "registry_get",
        "description": "Retrieve a registry entry by key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Registry key to look up."}
            },
            "required": ["key"],
        },
    },
    {
        "name": "registry_set",
        "description": "Create or update a registry entry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Registry key."},
                "value": {"type": "string", "description": "Value to store."},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "registry_delete",
        "description": "Delete a registry entry by key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Registry key to delete."}
            },
            "required": ["key"],
        },
    },
    {
        "name": "registry_list",
        "description": "List all registry keys, optionally filtered by a prefix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "description": "Optional prefix filter.",
                    "default": "",
                }
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# In-process tool executor (simulates filesystem_server / registry_server)
# ---------------------------------------------------------------------------


class ToolExecutor:
    """
    Executes tool calls locally, simulating the filesystem_server and
    registry_server MCP servers within authorized boundaries.

    The filesystem root is constrained to AGENT_FS_ROOT (env var).
    The registry is an in-memory dict backed by AGENT_REGISTRY_PATH (env var).
    """

    def __init__(self, fs_root: str, registry_path: str) -> None:
        """
        Initialise the executor.

        Args:
            fs_root: Authorised filesystem root directory.
            registry_path: Path to the JSON file used as persistent registry store.
        """
        self.fs_root = os.path.abspath(fs_root)
        self.registry_path = registry_path
        self._registry: dict[str, str] = self._load_registry()

    # ------------------------------------------------------------------
    # Registry persistence helpers
    # ------------------------------------------------------------------

    def _load_registry(self) -> dict[str, str]:
        """Load registry from disk; return empty dict if file absent or corrupt."""
        try:
            if os.path.exists(self.registry_path):
                with open(self.registry_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict):
                        return {str(k): str(v) for k, v in data.items()}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Registry load failed (%s); starting fresh.", exc)
        return {}

    def _save_registry(self) -> None:
        """Persist the in-memory registry to disk."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.registry_path)), exist_ok=True)
            with open(self.registry_path, "w", encoding="utf-8") as fh:
                json.dump(self._registry, fh, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.error("Registry save failed: %s", exc)

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------

    def _safe_path(self, path: str) -> str:
        """
        Resolve *path* relative to fs_root and verify it stays within bounds.

        Raises:
            PermissionError: If the resolved path escapes the authorised root.
        """
        resolved = os.path.abspath(os.path.join(self.fs_root, path.lstrip("/")))
        if not resolved.startswith(self.fs_root):
            raise PermissionError(
                f"Path '{path}' resolves outside authorised root '{self.fs_root}'."
            )
        return resolved

    # ------------------------------------------------------------------
    # Public dispatch
    # ------------------------------------------------------------------

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Dispatch a tool call and return a JSON-serialisable result string.

        Args:
            tool_name: Name of the tool to invoke.
            tool_input: Validated input dict for the tool.

        Returns:
            A JSON string describing the outcome.
        """
        dispatch = {
            "filesystem_read": self._fs_read,
            "filesystem_write": self._fs_write,
            "filesystem_update": self._fs_update,
            "filesystem_list": self._fs_list,
            "registry_get": self._reg_get,
            "registry_set": self._reg_set,
            "registry_delete": self._reg_delete,
            "registry_list": self._reg_list,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            return handler(tool_input)
        except PermissionError as exc:
            logger.error("Permission violation in tool '%s': %s", tool_name, exc)
            return json.dumps({"error": "permission_denied", "detail": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.error("Tool '%s' raised unexpected error: %s", tool_name, exc)
            return json.dumps({"error": "tool_execution_error", "detail": str(exc)})

    # ------------------------------------------------------------------
    # Filesystem tools
    # ------------------------------------------------------------------

    def _fs_read(self, inp: dict[str, Any]) -> str:
        path = self._safe_path(inp["path"])
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        return json.dumps({"path": path, "content": content})

    def _fs_write(self, inp: dict[str, Any]) -> str:
        path = self._safe_path(inp["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(inp["content"])
        return json.dumps({"path": path, "bytes_written": len(inp["content"])})

    def _fs_update(self, inp: dict[str, Any]) -> str:
        path = self._safe_path(inp["path"])
        mode = inp.get("mode", "append")
        if mode == "append":
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(inp["content"])
        elif mode == "prepend":
            existing = ""
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    existing = fh.read()
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(inp["content"] + existing)
        else:
            return json.dumps({"error": f"Unknown update mode: {mode}"})
        return json.dumps({"path": path, "mode": mode, "bytes_added": len(inp["content"])})

    def _fs_list(self, inp: dict[str, Any]) -> str:
        directory = self._safe_path(inp["directory"])
        entries = os.listdir(directory)
        return json.dumps({"directory": directory, "entries": entries})

    # ------------------------------------------------------------------
    # Registry tools
    # ------------------------------------------------------------------

    def _reg_get(self, inp: dict[str, Any]) -> str:
        key = inp["key"]
        value = self._registry.get(key)
        if value is None:
            return json.dumps({"error": "key_not_found", "key": key})
        return json.dumps({"key": key, "value": value})

    def _reg_set(self, inp: dict[str, Any]) -> str:
        key, value = inp["key"], inp["value"]
        self._registry[key] = value
        self._save_registry()
        return json.dumps({"key": key, "status": "set"})

    def _reg_delete(self, inp: dict[str, Any]) -> str:
        key = inp["key"]
        existed = key in self._registry
        self._registry.pop(key, None)
        if existed:
            self._save_registry()
        return json.dumps({"key": key, "deleted": existed})

    def _reg_list(self, inp: dict[str, Any]) -> str:
        prefix = inp.get("prefix", "")
        keys = [k for k in self._registry if k.startswith(prefix)]
        return json.dumps({"prefix": prefix, "keys": keys})


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ExistsAgent9273Aee3:
    """
    Production agent: exists_agent_9273aee3

    Department : general
    Model      : claude-sonnet-4-6

    Responsibilities
    ----------------
    - Parse, validate, and execute task payloads received from the general department
    - Perform file system operations including read, write, update, and organisational
      tasks within authorised boundaries
    - Maintain and query registry entries to support task tracking and metadata management
    - Produce structured completion and error reports for every task execution
    - Enforce data integrity by validating inputs and outputs against defined schemas
    - Monitor execution state and emit observability signals at each workflow checkpoint
    - Escalate unresolvable conflicts, boundary violations, or resource failures to the
      appropriate oversight channel
    """

    # System prompt injected into every conversation
    _SYSTEM_PROMPT = (
        "You are exists_agent_9273aee3, a precise and efficient AI agent serving the "
        "general department.\n\n"
        "Mission: Test mission. This agent supports the general department with its core "
        "responsibilities. It operates with precision and efficiency to fulfill its "
        "designated objectives.\n\n"
        "Responsibilities:\n"
        "1. Parse, validate, and execute task payloads received from the general department.\n"
        "2. Perform file system operations (read, write, update, list) within authorised boundaries.\n"
        "3. Maintain and query registry entries for task tracking and metadata management.\n"
        "4. Produce structured completion and error reports for every task execution.\n"
        "5. Enforce data integrity by validating inputs and outputs against defined schemas.\n"
        "6. Monitor execution state and emit observability signals at each workflow checkpoint.\n"
        "7. Escalate unresolvable conflicts, boundary violations, or resource failures.\n\n"
        "Allowed tools: filesystem_server, registry_server (exposed as individual tool functions).\n"
        "Always prefer tool use over assumptions. Be concise and factual in your final answer."
    )

    def __init__(self) -> None:
        """
        Initialise the agent by reading all configuration from environment variables.

        Required environment variables
        --------------------------------
        ANTHROPIC_API_KEY   : Anthropic API key.

        Optional environment variables
        --------------------------------
        AGENT_MODEL         : Model identifier (default: claude-sonnet-4-6).
        AGENT_MAX_TOKENS    : Maximum tokens per response (default: 4096).
        AGENT_MAX_ITERATIONS: Maximum agentic loop iterations (default: 20).
        AGENT_FS_ROOT       : Authorised filesystem root (default: /tmp/agent_fs).
        AGENT_REGISTRY_PATH : Path to registry JSON file (default: /tmp/agent_registry.json).
        AGENT_LOG_LEVEL     : Logging level string (default: INFO).
        """
        # Logging
        log_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

        # Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")
        try:
            self._client = anthropic.Anthropic(api_key=api_key)
        except Exception as exc:
            logger.error("Failed to initialise Anthropic client: %s", exc)
            raise

        # Model config
        self._model: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
        self._max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        self._max_iterations: int = int(os.getenv("AGENT_MAX_ITERATIONS", "20"))

        # Tool executor
        fs_root = os.getenv("AGENT_FS_ROOT", "/tmp/agent_fs")
        registry_path = os.getenv("AGENT_REGISTRY_PATH", "/tmp/agent_registry.json")
        os.makedirs(fs_root, exist_ok=True)
        self._executor = ToolExecutor(fs_root=fs_root, registry_path=registry_path)

        logger.info(
            "ExistsAgent9273Aee3 initialised | model=%s | fs_root=%s | registry=%s",
            self._model,
            fs_root,
            registry_path,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_task(self, task: str) -> TaskPayload:
        """
        Validate and wrap the raw task string in a TaskPayload schema.

        Args:
            task: Raw task string from the caller.

        Returns:
            A validated TaskPayload instance.

        Raises:
            ValidationError: If the task fails schema validation.
        """
        try:
            payload = TaskPayload(raw=task)
            logger.info("Task validated | received_at=%s", payload.received_at)
            return payload
        except ValidationError as exc:
            logger.error("Task validation failed: %s", exc)
            raise

    def _build_report(
        self,
        task: str,
        status: str,
        result: str,
        error_detail: str | None = None,
    ) -> CompletionReport:
        """
        Build a structured CompletionReport.

        Args:
            task: Original task string (used as summary).
            status: One of 'success', 'error', or 'escalated'.
            result: Human-readable result or error message.
            error_detail: Optional detailed error information.

        Returns:
            A validated CompletionReport instance.
        """
        return CompletionReport(
            task_summary=task[:200],
            status=status,
            result=result,
            error_detail=error_detail,
        )

    def _emit_checkpoint(self, checkpoint: str, detail: str = "") -> None:
        """
        Emit an observability signal at a workflow checkpoint.

        Args:
            checkpoint: Name of the checkpoint (e.g. 'task_received', 'tool_call').
            detail: Optional additional context.
        """
        logger.info("[CHECKPOINT] %s | %s", checkpoint, detail)

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Execute a single tool call via the ToolExecutor and return the result string.

        Args:
            tool_name: Name of the tool to invoke.
            tool_input: Input dict for the tool.

        Returns:
            JSON string result from the tool.
        """
        self._emit_checkpoint("tool_call", f"tool={tool_name} input={json.dumps(tool_input)[:200]}")
        try:
            result = self._executor.execute(tool_name, tool_input)
            self._emit_checkpoint("tool_result", f"tool={tool_name} result={result[:200]}")
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error executing tool '%s': %s", tool_name, exc)
            return json.dumps({"error": "unexpected_tool_error", "detail": str(exc)})

    # ------------------------------------------------------------------
    # Agentic loop
    # ------------------------------------------------------------------

    async def run(self, task: str) -> str:
        """
        Execute a task through the agentic loop and return a structured report.

        The method:
        1. Validates the incoming task payload.
        2. Sends the task to the model with available tools.
        3. Processes tool calls iteratively until the model produces a final answer
           or the maximum iteration limit is reached.
        4. Returns a JSON-serialised CompletionReport.

        Args:
            task: Natural-language task description from the general department.

        Returns:
            JSON string of a CompletionReport describing the outcome.
        """
        self._emit_checkpoint("task_received", f"task={task[:100]}")

        # Validate input
        try:
            payload = self._validate_task(task)
        except ValidationError as exc:
            report = self._build_report(
                task=task,
                status="error",
                result="Task validation failed.",
                error_detail=str(exc),
            )
            return report.model_dump_json()

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": payload.raw}
        ]

        iteration = 0
        final_text = ""

        while iteration < self._max_iterations:
            iteration += 1
            self._emit_checkpoint("llm_call", f"iteration={iteration}")

            # Call the model
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=self._SYSTEM_PROMPT,
                    tools=TOOLS,  # type: ignore[arg-type]
                    messages=messages,
                )
            except anthropic.AuthenticationError as exc:
                logger.error("Authentication error: %s", exc)
                report = self._build_report(
                    task=task,
                    status="error",
                    result="Authentication failure with the AI provider.",
                    error_detail=str(exc),
                )
                return report.model_dump_json()
            except anthropic.RateLimitError as exc:
                logger.error("Rate limit error: %s", exc)
                report = self._build_report(
                    task=task,
                    status="error",
                    result="Rate limit exceeded. Please retry later.",
                    error_detail=str(exc),
                )
                return report.model_dump_json()
            except anthropic.APIStatusError as exc:
                logger.error("API status error %s: %s", exc.status_code, exc.message)
                report = self._build_report(
                    task=task,
                    status="error",
                    result=f"API error (status {exc.status_code}).",
                    error_detail=exc.message,
                )
                return report.model_dump_json()
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected error during model call: %s", exc)
                report = self._build_report(
                    task=task,
                    status="error",
                    result="Unexpected error during model invocation.",
                    error_detail=str(exc),
                )
                return report.model_dump_json()

            self._emit_checkpoint("llm_response", f"stop_reason={response.stop_reason}")

            # Collect text and tool-use blocks
            tool_use_blocks = []
            text_blocks = []
            for block in response.content:
                if block.type == "text":
                    text_blocks.append(block.text)
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            if text_blocks:
                final_text = " ".join(text_blocks)

            # If no tool calls or model signals end_turn, we are done
            if response.stop_reason == "end_turn" or not tool_use_blocks:
                break

            # Append assistant message with all content blocks
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call and collect results
            tool_results = []
            for tool_block in tool_use_blocks:
                tool_result_content = self._process_tool_call(
                    tool_name=tool_block.name,
                    tool_input=tool_block.input,
                )
                # Check for escalation signals in tool results
                try:
                    result_data = json.loads(tool_result_content)
                    if result_data.get("error") == "permission_denied":
                        self._emit_checkpoint(
                            "escalation",
                            f"Boundary violation detected for tool '{tool_block.name}'.",
                        )
                except (json.JSONDecodeError, AttributeError):
                    pass

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": tool_result_content,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        else:
            # Max iterations reached — escalate
            self._emit_checkpoint("escalation", "Maximum iteration limit reached.")
            report = self._build_report(
                task=task,
                status="escalated",
                result="Task could not be completed within the maximum iteration limit.",
                error_detail=f"Reached {self._max_iterations} iterations without a final answer.",
            )
            return report.model_dump_json()

        self._emit_checkpoint("task_complete", f"status=success iterations={iteration}")
        report = self._build_report(
            task=task,
            status="success",
            result=final_text or "Task completed successfully.",
        )
        return report.model_dump_json()


# ---------------------------------------------------------------------------
# Entrypoint (for quick manual testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        """Run a quick smoke-test task."""
        agent = ExistsAgent9273Aee3()
        sample_task = (
            "List the files in the root directory, then store a registry entry "
            "with key 'smoke_test' and value 'passed'."
        )
        result = await agent.run(sample_task)
        print(result)

    asyncio.run(_main())