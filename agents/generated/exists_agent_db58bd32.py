"""
exists_agent_db58bd32.py

Production agent for the 'general' department.
Mission: Test mission. This agent supports the general department in achieving
its objectives. It operates with precision and efficiency to fulfill assigned tasks.
"""

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
# Observability helpers
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("exists_agent_db58bd32")


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------


class TaskSpec(BaseModel):
    """Validated representation of an incoming task."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_task: str
    received_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CompletionReport(BaseModel):
    """Structured completion report delivered to the department coordinator."""

    task_id: str
    agent_name: str = "exists_agent_db58bd32"
    department: str = "general"
    status: str  # "success" | "failure"
    result: str
    retries_used: int
    duration_seconds: float
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Tool definitions (filesystem_server + registry_server)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "filesystem_read",
        "description": (
            "Read the contents of a file from the filesystem. "
            "Part of filesystem_server toolset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "filesystem_write",
        "description": (
            "Write content to a file on the filesystem. "
            "Part of filesystem_server toolset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write into the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "filesystem_list",
        "description": (
            "List files and directories at a given path. "
            "Part of filesystem_server toolset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "registry_get",
        "description": (
            "Retrieve a value from the registry by key. "
            "Part of registry_server toolset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Registry key to look up.",
                }
            },
            "required": ["key"],
        },
    },
    {
        "name": "registry_set",
        "description": (
            "Store a value in the registry under a given key. "
            "Part of registry_server toolset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Registry key.",
                },
                "value": {
                    "type": "string",
                    "description": "Value to store.",
                },
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "registry_delete",
        "description": (
            "Delete a key from the registry. "
            "Part of registry_server toolset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Registry key to delete.",
                }
            },
            "required": ["key"],
        },
    },
]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ExistsAgentDb58Bd32:
    """
    Production agent: exists_agent_db58bd32
    Department: general

    Responsibilities
    ----------------
    - Parse and validate all incoming task specifications before execution
    - Perform registry and filesystem operations required to fulfill assigned tasks
    - Apply defined decision rules to navigate ambiguous or error conditions
    - Produce structured, schema-conformant outputs for all assigned tasks
    - Emit observability logs and metrics for every task execution
    - Deliver completion reports to the department coordinator upon task finish
    - Maintain compliance with allowed_tools list and non_responsibilities boundaries
    - Retry failed tool operations according to retry_policy before escalating
    """

    # Allowed tool server namespaces
    ALLOWED_TOOLS = {"filesystem_server", "registry_server"}

    def __init__(self) -> None:
        """
        Initialise the agent by reading all configuration from environment
        variables.

        Required environment variables
        --------------------------------
        ANTHROPIC_API_KEY        : Anthropic API key.

        Optional environment variables
        --------------------------------
        AGENT_MAX_TOKENS         : Maximum tokens for model responses (default 4096).
        AGENT_MAX_RETRIES        : Maximum retry attempts for failed tool calls (default 3).
        AGENT_RETRY_DELAY        : Seconds to wait between retries (default 2.0).
        AGENT_MAX_ITERATIONS     : Maximum agentic loop iterations (default 20).
        COORDINATOR_ENDPOINT     : URL of the department coordinator (default empty).
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model: str = "claude-sonnet-4-6"
        self.max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        self.max_retries: int = int(os.getenv("AGENT_MAX_RETRIES", "3"))
        self.retry_delay: float = float(os.getenv("AGENT_RETRY_DELAY", "2.0"))
        self.max_iterations: int = int(os.getenv("AGENT_MAX_ITERATIONS", "20"))
        self.coordinator_endpoint: str = os.getenv("COORDINATOR_ENDPOINT", "")

        self._system_prompt: str = (
            "You are exists_agent_db58bd32, a precise and efficient AI agent "
            "operating within the 'general' department.\n\n"
            "Mission: Test mission. This agent supports the general department "
            "in achieving its objectives. It operates with precision and "
            "efficiency to fulfill assigned tasks.\n\n"
            "You have access to two tool servers:\n"
            "  • filesystem_server — read, write, and list files.\n"
            "  • registry_server  — get, set, and delete registry keys.\n\n"
            "Rules:\n"
            "1. Always validate the task before acting.\n"
            "2. Use only the tools listed above.\n"
            "3. On tool failure, apply retry logic before escalating.\n"
            "4. Produce structured, schema-conformant outputs.\n"
            "5. Emit clear reasoning for every decision.\n"
            "6. When the task is complete, summarise the outcome concisely."
        )

        logger.info(
            "ExistsAgentDb58Bd32 initialised | model=%s max_tokens=%d "
            "max_retries=%d max_iterations=%d",
            self.model,
            self.max_tokens,
            self.max_retries,
            self.max_iterations,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, task: str) -> str:
        """
        Execute a task end-to-end and return a JSON-serialised
        CompletionReport.

        Parameters
        ----------
        task : str
            Natural-language task description.

        Returns
        -------
        str
            JSON string conforming to the CompletionReport schema.
        """
        start_time = time.monotonic()
        retries_used = 0

        # 1. Validate incoming task spec
        try:
            spec = self._parse_task(task)
        except Exception as exc:
            logger.error("Task validation failed: %s", exc)
            return self._build_report(
                task_id=str(uuid.uuid4()),
                status="failure",
                result=f"Task validation error: {exc}",
                retries_used=0,
                start_time=start_time,
            )

        logger.info("Task accepted | task_id=%s", spec.task_id)
        self._emit_metric("task_received", {"task_id": spec.task_id})

        # 2. Agentic loop
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": spec.raw_task}
        ]

        final_result = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(
                "Agentic loop iteration %d/%d | task_id=%s",
                iteration,
                self.max_iterations,
                spec.task_id,
            )

            # 3. Call the model (with retry)
            response = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=self._system_prompt,
                        tools=TOOLS,
                        messages=messages,
                    )
                    break
                except anthropic.APIConnectionError as exc:
                    logger.warning(
                        "API connection error (attempt %d/%d): %s",
                        attempt,
                        self.max_retries,
                        exc,
                    )
                    retries_used += 1
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                except anthropic.RateLimitError as exc:
                    logger.warning(
                        "Rate limit hit (attempt %d/%d): %s",
                        attempt,
                        self.max_retries,
                        exc,
                    )
                    retries_used += 1
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay * attempt)
                except anthropic.APIStatusError as exc:
                    logger.error("API status error: %s", exc)
                    retries_used += 1
                    break
                except Exception as exc:
                    logger.error("Unexpected error calling model: %s", exc)
                    retries_used += 1
                    break

            if response is None:
                final_result = "Model call failed after all retries."
                logger.error(final_result)
                break

            self._emit_metric(
                "model_response",
                {
                    "task_id": spec.task_id,
                    "stop_reason": response.stop_reason,
                    "iteration": iteration,
                },
            )

            # 4. Append assistant message
            messages.append({"role": "assistant", "content": response.content})

            # 5. Check stop condition
            if response.stop_reason == "end_turn":
                final_result = self._extract_text(response.content)
                logger.info(
                    "Task completed | task_id=%s iterations=%d",
                    spec.task_id,
                    iteration,
                )
                break

            # 6. Handle tool use
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_result = self._execute_tool(
                        tool_name=block.name,
                        tool_input=block.input,
                        task_id=spec.task_id,
                    )
                    retries_used += tool_result.get("retries", 0)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result["content"],
                        }
                    )

                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            final_result = (
                f"Unexpected stop_reason '{response.stop_reason}'. "
                "Terminating loop."
            )
            logger.warning(final_result)
            break

        else:
            final_result = (
                f"Reached maximum iterations ({self.max_iterations}) "
                "without completing the task."
            )
            logger.warning(final_result)

        # 7. Build and deliver completion report
        report_json = self._build_report(
            task_id=spec.task_id,
            status="success" if "error" not in final_result.lower() else "failure",
            result=final_result,
            retries_used=retries_used,
            start_time=start_time,
        )

        self._deliver_report(report_json, spec.task_id)
        return report_json

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_task(self, raw_task: str) -> TaskSpec:
        """
        Parse and validate the raw task string into a TaskSpec model.

        Parameters
        ----------
        raw_task : str
            Raw task string from the caller.

        Returns
        -------
        TaskSpec
            Validated task specification.

        Raises
        ------
        ValueError
            If the task string is empty or invalid.
        """
        if not raw_task or not raw_task.strip():
            raise ValueError("Task string must not be empty.")
        return TaskSpec(raw_task=raw_task.strip())

    def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        task_id: str,
    ) -> dict[str, Any]:
        """
        Dispatch a tool call to the appropriate handler with retry logic.

        Parameters
        ----------
        tool_name : str
            Name of the tool to invoke.
        tool_input : dict
            Input parameters for the tool.
        task_id : str
            Current task identifier for logging.

        Returns
        -------
        dict
            Dictionary with keys 'content' (str result) and 'retries' (int).
        """
        logger.info(
            "Tool call | task_id=%s tool=%s input=%s",
            task_id,
            tool_name,
            json.dumps(tool_input),
        )
        self._emit_metric(
            "tool_call",
            {"task_id": task_id, "tool": tool_name},
        )

        handler_map = {
            "filesystem_read": self._tool_filesystem_read,
            "filesystem_write": self._tool_filesystem_write,
            "filesystem_list": self._tool_filesystem_list,
            "registry_get": self._tool_registry_get,
            "registry_set": self._tool_registry_set,
            "registry_delete": self._tool_registry_delete,
        }

        handler = handler_map.get(tool_name)
        if handler is None:
            msg = f"Tool '{tool_name}' is not in the allowed_tools list."
            logger.error(msg)
            return {"content": f"ERROR: {msg}", "retries": 0}

        retries = 0
        for attempt in range(1, self.max_retries + 1):
            try:
                result = handler(tool_input)
                self._emit_metric(
                    "tool_success",
                    {"task_id": task_id, "tool": tool_name, "attempt": attempt},
                )
                return {"content": result, "retries": retries}
            except Exception as exc:
                retries += 1
                logger.warning(
                    "Tool '%s' failed (attempt %d/%d): %s",
                    tool_name,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        error_msg = (
            f"Tool '{tool_name}' failed after {self.max_retries} attempts."
        )
        logger.error(error_msg)
        self._emit_metric(
            "tool_failure",
            {"task_id": task_id, "tool": tool_name},
        )
        return {"content": f"ERROR: {error_msg}", "retries": retries}

    # ------------------------------------------------------------------
    # Tool handlers — filesystem_server
    # ------------------------------------------------------------------

    def _tool_filesystem_read(self, params: dict[str, Any]) -> str:
        """
        Read a file from the local filesystem.

        Parameters
        ----------
        params : dict
            Must contain 'path' key.

        Returns
        -------
        str
            File contents as a string.
        """
        path = params["path"]
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        logger.info("filesystem_read | path=%s bytes=%d", path, len(content))
        return content

    def _tool_filesystem_write(self, params: dict[str, Any]) -> str:
        """
        Write content to a file on the local filesystem.

        Parameters
        ----------
        params : dict
            Must contain 'path' and 'content' keys.

        Returns
        -------
        str
            Confirmation message.
        """
        path = params["path"]
        content = params["content"]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.info("filesystem_write | path=%s bytes=%d", path, len(content))
        return f"Written {len(content)} bytes to '{path}'."

    def _tool_filesystem_list(self, params: dict[str, Any]) -> str:
        """
        List directory contents on the local filesystem.

        Parameters
        ----------
        params : dict
            Must contain 'path' key.

        Returns
        -------
        str
            JSON array of entry names.
        """
        path = params["path"]
        entries = os.listdir(path)
        logger.info("filesystem_list | path=%s entries=%d", path, len(entries))
        return json.dumps(entries)

    # ------------------------------------------------------------------
    # Tool handlers — registry_server
    # ------------------------------------------------------------------

    def _tool_registry_get(self, params: dict[str, Any]) -> str:
        """
        Retrieve a value from the in-process registry store.

        Parameters
        ----------
        params : dict
            Must contain 'key'.

        Returns
        -------
        str
            Stored value or a not-found message.
        """
        key = params["key"]
        value = self._registry_store().get(key)
        if value is None:
            return f"Key '{key}' not found in registry."
        logger.info("registry_get | key=%s", key)
        return value

    def _tool_registry_set(self, params: dict[str, Any]) -> str:
        """
        Store a value in the in-process registry store.

        Parameters
        ----------
        params : dict
            Must contain 'key' and 'value'.

        Returns
        -------
        str
            Confirmation message.
        """
        key = params["key"]
        value = params["value"]
        store = self._registry_store()
        store[key] = value
        logger.info("registry_set | key=%s", key)
        return f"Key '{key}' set successfully."

    def _tool_registry_delete(self, params: dict[str, Any]) -> str:
        """
        Delete a key from the in-process registry store.

        Parameters
        ----------
        params : dict
            Must contain 'key'.

        Returns
        -------
        str
            Confirmation or not-found message.
        """
        key = params["key"]
        store = self._registry_store()
        if key in store:
            del store[key]
            logger.info("registry_delete | key=%s", key)
            return f"Key '{key}' deleted."
        return f"Key '{key}' not found; nothing deleted."

    def _registry_store(self) -> dict[str, str]:
        """
        Return the singleton in-process registry dictionary.

        Returns
        -------
        dict
            Mutable registry store shared across tool calls within this
            agent instance.
        """
        if not hasattr(self, "_registry"):
            self._registry: dict[str, str] = {}
        return self._registry

    # ------------------------------------------------------------------
    # Reporting & observability
    # ------------------------------------------------------------------

    def _build_report(
        self,
        task_id: str,
        status: str,
        result: str,
        retries_used: int,
        start_time: float,
    ) -> str:
        """
        Build a JSON-serialised CompletionReport.

        Parameters
        ----------
        task_id : str
            Unique task identifier.
        status : str
            'success' or 'failure'.
        result : str
            Human-readable outcome description.
        retries_used : int
            Total retry attempts consumed during execution.
        start_time : float
            Monotonic start time (from time.monotonic()).

        Returns
        -------
        str
            JSON string of the CompletionReport.
        """
        duration = time.monotonic() - start_time
        report = CompletionReport(
            task_id=task_id,
            status=status,
            result=result,
            retries_used=retries_used,
            duration_seconds=round(duration, 3),
        )
        self._emit_metric(
            "task_completed",
            {
                "task_id": task_id,
                "status": status,
                "duration_seconds": report.duration_seconds,
                "retries_used": retries_used,
            },
        )
        return report.model_dump_json(indent=2)

    def _deliver_report(self, report_json: str, task_id: str) -> None:
        """
        Deliver the completion report to the department coordinator.

        If COORDINATOR_ENDPOINT is set, the report is POSTed via urllib.
        Otherwise it is logged locally.

        Parameters
        ----------
        report_json : str
            JSON-serialised CompletionReport.
        task_id : str
            Task identifier for log correlation.
        """
        if not self.coordinator_endpoint:
            logger.info(
                "Completion report (no coordinator configured) | task_id=%s\n%s",
                task_id,
                report_json,
            )
            return

        import urllib.request  # stdlib — imported here to keep top-level clean

        try:
            data = report_json.encode("utf-8")
            req = urllib.request.Request(
                self.coordinator_endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(
                    "Report delivered | task_id=%s status=%d",
                    task_id,
                    resp.status,
                )
        except Exception as exc:
            logger.error(
                "Failed to deliver report to coordinator | task_id=%s error=%s",
                task_id,
                exc,
            )

    def _emit_metric(self, event: str, data: dict[str, Any]) -> None:
        """
        Emit a structured observability metric to the log stream.

        Parameters
        ----------
        event : str
            Event name / metric key.
        data : dict
            Arbitrary key-value pairs associated with the event.
        """
        payload = {"event": event, "agent": "exists_agent_db58bd32", **data}
        logger.info("METRIC %s", json.dumps(payload))

    @staticmethod
    def _extract_text(content: list[Any]) -> str:
        """
        Extract plain text from an Anthropic message content list.

        Parameters
        ----------
        content : list
            List of content blocks returned by the Anthropic API.

        Returns
        -------
        str
            Concatenated text from all TextBlock entries.
        """
        parts = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts).strip()