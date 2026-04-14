"""
exists_agent_857b124b.py

Production agent for the general department.
Mission: Test mission. This agent supports the general department in carrying out
its core responsibilities. It operates with precision and reliability to fulfill
assigned tasks.
"""

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("exists_agent_857b124b")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TaskSpec(BaseModel):
    """Validated representation of an incoming task."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_task: str
    received_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    department: str = "general"


class CheckpointData(BaseModel):
    """Checkpoint state persisted throughout the execution lifecycle."""

    task_id: str
    status: str = "pending"
    steps_completed: list[str] = Field(default_factory=list)
    tool_calls_made: int = 0
    last_updated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    result: str | None = None
    error: str | None = None


class AgentConfig(BaseModel):
    """All runtime configuration loaded from environment variables."""

    api_key: str
    model: str
    max_tokens: int
    max_retries: int
    retry_delay_seconds: float
    token_budget: int
    department: str
    agent_name: str


# ---------------------------------------------------------------------------
# Tool definitions (filesystem_server + registry_server)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "filesystem_server",
        "description": (
            "Interact with the filesystem server. Supports operations: "
            "read_file, write_file, list_directory, delete_file, file_exists. "
            "Use this tool to read, write, or manage files and directories."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "read_file",
                        "write_file",
                        "list_directory",
                        "delete_file",
                        "file_exists",
                    ],
                    "description": "The filesystem operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path for the operation.",
                },
                "content": {
                    "type": "string",
                    "description": "File content (required for write_file).",
                },
            },
            "required": ["operation", "path"],
        },
    },
    {
        "name": "registry_server",
        "description": (
            "Interact with the registry server. Supports operations: "
            "get_value, set_value, delete_key, list_keys, key_exists. "
            "Use this tool to read or write key-value data in the registry."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "get_value",
                        "set_value",
                        "delete_key",
                        "list_keys",
                        "key_exists",
                    ],
                    "description": "The registry operation to perform.",
                },
                "key": {
                    "type": "string",
                    "description": "Registry key path.",
                },
                "value": {
                    "type": "string",
                    "description": "Value to store (required for set_value).",
                },
                "namespace": {
                    "type": "string",
                    "description": "Optional namespace / prefix for the key.",
                    "default": "general",
                },
            },
            "required": ["operation", "key"],
        },
    },
]


# ---------------------------------------------------------------------------
# Simulated tool execution (replace with real server calls in production)
# ---------------------------------------------------------------------------


def _execute_filesystem_server(tool_input: dict[str, Any]) -> str:
    """
    Execute a filesystem_server tool call.

    In production this would call the actual filesystem microservice.
    Here we simulate responses so the agent loop can run end-to-end.

    Args:
        tool_input: Validated input dict matching the tool schema.

    Returns:
        JSON-encoded string result from the filesystem server.
    """
    operation = tool_input.get("operation", "")
    path = tool_input.get("path", "")
    content = tool_input.get("content", "")

    logger.info("filesystem_server | operation=%s path=%s", operation, path)

    if operation == "read_file":
        return json.dumps({"status": "ok", "content": f"<contents of {path}>", "path": path})
    if operation == "write_file":
        return json.dumps({"status": "ok", "bytes_written": len(content), "path": path})
    if operation == "list_directory":
        return json.dumps({"status": "ok", "entries": [], "path": path})
    if operation == "delete_file":
        return json.dumps({"status": "ok", "deleted": path})
    if operation == "file_exists":
        return json.dumps({"status": "ok", "exists": False, "path": path})

    return json.dumps({"status": "error", "message": f"Unknown operation: {operation}"})


def _execute_registry_server(tool_input: dict[str, Any]) -> str:
    """
    Execute a registry_server tool call.

    In production this would call the actual registry microservice.
    Here we simulate responses so the agent loop can run end-to-end.

    Args:
        tool_input: Validated input dict matching the tool schema.

    Returns:
        JSON-encoded string result from the registry server.
    """
    operation = tool_input.get("operation", "")
    key = tool_input.get("key", "")
    value = tool_input.get("value", "")
    namespace = tool_input.get("namespace", "general")

    logger.info(
        "registry_server | operation=%s namespace=%s key=%s", operation, namespace, key
    )

    if operation == "get_value":
        return json.dumps({"status": "ok", "key": key, "value": None, "namespace": namespace})
    if operation == "set_value":
        return json.dumps({"status": "ok", "key": key, "value": value, "namespace": namespace})
    if operation == "delete_key":
        return json.dumps({"status": "ok", "deleted": key, "namespace": namespace})
    if operation == "list_keys":
        return json.dumps({"status": "ok", "keys": [], "namespace": namespace})
    if operation == "key_exists":
        return json.dumps({"status": "ok", "exists": False, "key": key, "namespace": namespace})

    return json.dumps({"status": "error", "message": f"Unknown operation: {operation}"})


def _dispatch_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """
    Route a tool call to the appropriate server handler.

    Args:
        tool_name: Name of the tool as declared in TOOLS.
        tool_input: Input payload for the tool.

    Returns:
        String result from the tool handler.

    Raises:
        ValueError: If the tool name is not recognised.
    """
    if tool_name == "filesystem_server":
        return _execute_filesystem_server(tool_input)
    if tool_name == "registry_server":
        return _execute_registry_server(tool_input)
    raise ValueError(f"Unknown tool: {tool_name}")


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class ExistsAgent857B124B:
    """
    Production agent for the general department.

    Responsibilities:
    - Parse and validate all incoming task specifications before execution.
    - Execute assigned general department tasks using filesystem_server and
      registry_server.
    - Maintain accurate task state and checkpoint data throughout the execution
      lifecycle.
    - Log all operations with sufficient detail to support audit and debugging.
    - Validate all outputs against task objectives before marking tasks complete.
    - Escalate unresolvable errors or out-of-scope requests promptly with full
      context.
    - Adhere strictly to token budget and retry policy constraints.
    """

    # System prompt injected into every conversation
    SYSTEM_PROMPT = (
        "You are exists_agent_857b124b, a precise and reliable AI agent operating "
        "within the general department.\n\n"
        "Mission: Test mission. This agent supports the general department in "
        "carrying out its core responsibilities. It operates with precision and "
        "reliability to fulfill assigned tasks.\n\n"
        "Responsibilities:\n"
        "1. Parse and validate all incoming task specifications before execution.\n"
        "2. Execute assigned general department tasks using filesystem_server and "
        "registry_server.\n"
        "3. Maintain accurate task state and checkpoint data throughout the execution "
        "lifecycle.\n"
        "4. Log all operations with sufficient detail to support audit and debugging.\n"
        "5. Validate all outputs against task objectives before marking tasks complete.\n"
        "6. Escalate unresolvable errors or out-of-scope requests promptly with full "
        "context.\n"
        "7. Adhere strictly to token budget and retry policy constraints.\n\n"
        "Allowed tools: filesystem_server, registry_server.\n"
        "Always reason step-by-step. When a task is complete, provide a concise "
        "summary of what was accomplished."
    )

    def __init__(self) -> None:
        """
        Initialise the agent by reading all configuration from environment variables.

        Environment variables:
            ANTHROPIC_API_KEY       – Anthropic API key (required).
            AGENT_MODEL             – Model identifier (default: claude-sonnet-4-6).
            AGENT_MAX_TOKENS        – Max tokens per API response (default: 4096).
            AGENT_MAX_RETRIES       – Max retry attempts on transient errors (default: 3).
            AGENT_RETRY_DELAY       – Seconds between retries (default: 2.0).
            AGENT_TOKEN_BUDGET      – Total token budget per task (default: 50000).
            AGENT_DEPARTMENT        – Department name (default: general).
            AGENT_NAME              – Agent name (default: exists_agent_857b124b).

        Raises:
            EnvironmentError: If ANTHROPIC_API_KEY is not set.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is required but not set."
            )

        try:
            self.config = AgentConfig(
                api_key=api_key,
                model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
                max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "4096")),
                max_retries=int(os.getenv("AGENT_MAX_RETRIES", "3")),
                retry_delay_seconds=float(os.getenv("AGENT_RETRY_DELAY", "2.0")),
                token_budget=int(os.getenv("AGENT_TOKEN_BUDGET", "50000")),
                department=os.getenv("AGENT_DEPARTMENT", "general"),
                agent_name=os.getenv("AGENT_NAME", "exists_agent_857b124b"),
            )
        except (ValueError, ValidationError) as exc:
            logger.error("Failed to build AgentConfig: %s", exc)
            raise

        try:
            self._client = anthropic.Anthropic(api_key=self.config.api_key)
        except Exception as exc:
            logger.error("Failed to initialise Anthropic client: %s", exc)
            raise

        self._total_tokens_used: int = 0
        logger.info(
            "Agent %s initialised | model=%s | department=%s",
            self.config.agent_name,
            self.config.model,
            self.config.department,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, task: str) -> str:
        """
        Execute a task end-to-end and return the final result string.

        The method:
        1. Validates and parses the incoming task specification.
        2. Initialises a checkpoint record.
        3. Runs the agentic loop (model → tool calls → model) until the model
           stops requesting tools or the token budget is exhausted.
        4. Validates the final output against the original task objective.
        5. Returns the validated result or an escalation message.

        Args:
            task: Natural-language task description for the agent to execute.

        Returns:
            A string containing the final result or an escalation notice.
        """
        # Step 1 – validate task spec
        try:
            task_spec = self._parse_task(task)
        except ValidationError as exc:
            escalation = self._escalate(
                task_id="unknown",
                reason="Task specification failed validation.",
                detail=str(exc),
            )
            logger.error("Task validation failed: %s", exc)
            return escalation

        checkpoint = CheckpointData(task_id=task_spec.task_id)
        logger.info(
            "Task %s started | department=%s", task_spec.task_id, task_spec.department
        )

        # Step 2 – run agentic loop
        try:
            result = await self._agent_loop(task_spec, checkpoint)
        except Exception as exc:
            checkpoint.status = "error"
            checkpoint.error = str(exc)
            self._update_checkpoint(checkpoint)
            escalation = self._escalate(
                task_id=task_spec.task_id,
                reason="Unrecoverable error during agent loop.",
                detail=str(exc),
            )
            logger.error("Agent loop failed for task %s: %s", task_spec.task_id, exc)
            return escalation

        # Step 3 – validate output
        if not self._validate_output(result, task_spec):
            checkpoint.status = "validation_failed"
            self._update_checkpoint(checkpoint)
            escalation = self._escalate(
                task_id=task_spec.task_id,
                reason="Output validation failed; result does not satisfy task objectives.",
                detail=f"Result: {result[:500]}",
            )
            logger.warning("Output validation failed for task %s", task_spec.task_id)
            return escalation

        checkpoint.status = "complete"
        checkpoint.result = result
        self._update_checkpoint(checkpoint)
        logger.info("Task %s completed successfully.", task_spec.task_id)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_task(self, raw_task: str) -> TaskSpec:
        """
        Parse and validate the raw task string into a TaskSpec model.

        Args:
            raw_task: Raw task string provided by the caller.

        Returns:
            A validated TaskSpec instance.

        Raises:
            ValidationError: If the task string fails Pydantic validation.
            ValueError: If the task string is empty or whitespace-only.
        """
        if not raw_task or not raw_task.strip():
            raise ValueError("Task string must not be empty.")
        spec = TaskSpec(raw_task=raw_task.strip(), department=self.config.department)
        logger.info("Parsed task spec: task_id=%s", spec.task_id)
        return spec

    def _update_checkpoint(self, checkpoint: CheckpointData) -> None:
        """
        Persist checkpoint data to the registry server.

        Failures are logged but do not raise so the main execution path is
        not interrupted by checkpoint persistence errors.

        Args:
            checkpoint: Current checkpoint state to persist.
        """
        checkpoint.last_updated = datetime.now(timezone.utc).isoformat()
        try:
            payload = checkpoint.model_dump_json()
            _execute_registry_server(
                {
                    "operation": "set_value",
                    "key": f"checkpoints/{checkpoint.task_id}",
                    "value": payload,
                    "namespace": self.config.department,
                }
            )
            logger.debug("Checkpoint persisted for task %s", checkpoint.task_id)
        except Exception as exc:
            logger.warning(
                "Failed to persist checkpoint for task %s: %s", checkpoint.task_id, exc
            )

    def _validate_output(self, result: str, task_spec: TaskSpec) -> bool:
        """
        Validate the agent's final output against the original task objective.

        Checks that the result is non-empty and contains substantive content
        rather than an error or empty response.

        Args:
            result: The final result string produced by the agent loop.
            task_spec: The original validated task specification.

        Returns:
            True if the output is considered valid, False otherwise.
        """
        if not result or not result.strip():
            logger.warning("Output validation: result is empty.")
            return False
        if result.strip().lower().startswith("escalation:"):
            # Already an escalation – treat as invalid output
            return False
        logger.debug("Output validation passed for task %s", task_spec.task_id)
        return True

    def _escalate(self, task_id: str, reason: str, detail: str) -> str:
        """
        Format and return an escalation message with full context.

        Args:
            task_id: Identifier of the task being escalated.
            reason: Human-readable reason for escalation.
            detail: Additional context (error messages, partial results, etc.).

        Returns:
            A formatted escalation string.
        """
        message = (
            f"ESCALATION | agent={self.config.agent_name} "
            f"| department={self.config.department} "
            f"| task_id={task_id} "
            f"| reason={reason} "
            f"| detail={detail} "
            f"| timestamp={datetime.now(timezone.utc).isoformat()}"
        )
        logger.error(message)
        return message

    def _check_token_budget(self, usage: anthropic.types.Usage) -> bool:
        """
        Check whether the cumulative token usage is within the configured budget.

        Args:
            usage: Token usage object returned by the Anthropic API.

        Returns:
            True if still within budget, False if the budget is exhausted.
        """
        self._total_tokens_used += usage.input_tokens + usage.output_tokens
        within_budget = self._total_tokens_used < self.config.token_budget
        if not within_budget:
            logger.warning(
                "Token budget exhausted: used=%d budget=%d",
                self._total_tokens_used,
                self.config.token_budget,
            )
        return within_budget

    def _call_model_with_retry(
        self, messages: list[dict[str, Any]]
    ) -> anthropic.types.Message:
        """
        Call the Anthropic API with exponential-backoff retry logic.

        Args:
            messages: The full conversation message list to send.

        Returns:
            The API response Message object.

        Raises:
            anthropic.APIError: If all retry attempts are exhausted.
            Exception: For unexpected errors that are not retried.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=self.SYSTEM_PROMPT,
                    tools=TOOLS,  # type: ignore[arg-type]
                    messages=messages,
                )
                logger.debug(
                    "API call succeeded on attempt %d | stop_reason=%s",
                    attempt,
                    response.stop_reason,
                )
                return response
            except anthropic.RateLimitError as exc:
                last_exc = exc
                wait = self.config.retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Rate limit hit (attempt %d/%d). Retrying in %.1fs.",
                    attempt,
                    self.config.max_retries,
                    wait,
                )
                time.sleep(wait)
            except anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code and exc.status_code >= 500:
                    wait = self.config.retry_delay_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "Server error %d (attempt %d/%d). Retrying in %.1fs.",
                        exc.status_code,
                        attempt,
                        self.config.max_retries,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    # 4xx errors are not retried
                    logger.error("Non-retryable API error: %s", exc)
                    raise
            except anthropic.APIConnectionError as exc:
                last_exc = exc
                wait = self.config.retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Connection error (attempt %d/%d). Retrying in %.1fs.",
                    attempt,
                    self.config.max_retries,
                    wait,
                )
                time.sleep(wait)
            except Exception as exc:
                logger.error("Unexpected error calling Anthropic API: %s", exc)
                raise

        raise last_exc or RuntimeError("All retry attempts exhausted.")

    async def _agent_loop(
        self, task_spec: TaskSpec, checkpoint: CheckpointData
    ) -> str:
        """
        Run the core agentic loop: model → tool calls → model until done.

        The loop continues until:
        - The model returns stop_reason == "end_turn" (no more tool calls).
        - The token budget is exhausted.
        - The maximum number of loop iterations is reached (safety cap).

        Args:
            task_spec: Validated task specification.
            checkpoint: Mutable checkpoint record updated throughout execution.

        Returns:
            The final text response from the model.

        Raises:
            RuntimeError: If the loop exits without producing a text response.
        """
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": task_spec.raw_task}
        ]

        checkpoint.status = "running"
        self._update_checkpoint(checkpoint)

        max_iterations = 50  # safety cap
        final_text: str = ""

        for iteration in range(max_iterations):
            logger.info(
                "Agent loop iteration %d | task=%s | tokens_used=%d",
                iteration + 1,
                task_spec.task_id,
                self._total_tokens_used,
            )

            # Call the model
            try:
                response = self._call_model_with_retry(messages)
            except Exception as exc:
                raise RuntimeError(f"Model call failed: {exc}") from exc

            # Check token budget
            if not self._check_token_budget(response.usage):
                logger.warning(
                    "Stopping agent loop: token budget exhausted at iteration %d.",
                    iteration + 1,
                )
                # Return whatever text we have so far
                break

            # Extract text content from the response
            text_parts: list[str] = []
            tool_use_blocks: list[anthropic.types.ToolUseBlock] = []

            for block in response.content:
                if isinstance(block, anthropic.types.TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, anthropic.types.ToolUseBlock):
                    tool_use_blocks.append(block)

            if text_parts:
                final_text = "\n".join(text_parts)

            # If no tool calls, we are done
            if response.stop_reason == "end_turn" or not tool_use_blocks:
                logger.info(
                    "Agent loop complete at iteration %d | stop_reason=%s",
                    iteration + 1,
                    response.stop_reason,
                )
                break

            # Append assistant message to conversation
            messages.append({"role": "assistant", "content": response.content})

            # Execute tool calls and collect results
            tool_results: list[dict[str, Any]] = []
            for tool_block in tool_use_blocks:
                checkpoint.tool_calls_made += 1
                checkpoint.steps_completed.append(
                    f"iter={iteration+1} tool={tool_block.name} id={tool_block.id}"
                )
                self._update_checkpoint(checkpoint)

                try:
                    tool_result_content = _dispatch_tool(
                        tool_block.name, tool_block.input  # type: ignore[arg-type]
                    )
                    logger.info(
                        "Tool %s executed successfully | id=%s",
                        tool_block.name,
                        tool_block.id,
                    )
                except ValueError as exc:
                    tool_result_content = json.dumps(
                        {"status": "error", "message": str(exc)}
                    )
                    logger.error(
                        "Tool dispatch error for %s: %s", tool_block.name, exc
                    )
                except Exception as exc:
                    tool_result_content = json.dumps(
                        {"status": "error", "message": f"Unexpected error: {exc}"}
                    )
                    logger.error(
                        "Unexpected error executing tool %s: %s", tool_block.name, exc
                    )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": tool_result_content,
                    }
                )

            # Append tool results as a user message
            messages.append({"role": "user", "content": tool_results})

        else:
            logger.warning(
                "Agent loop reached maximum iterations (%d) for task %s.",
                max_iterations,
                task_spec.task_id,
            )

        if not final_text:
            raise RuntimeError(
                "Agent loop completed without producing a text response."
            )

        return final_text


# ---------------------------------------------------------------------------
# Module-level entry point for quick testing
# ---------------------------------------------------------------------------


async def _main() -> None:
    """Run a quick smoke-test of the agent from the command line."""
    import asyncio  # noqa: F401 – already imported implicitly via async def

    agent = ExistsAgent857B124B()
    test_task = (
        "List all files in the current working directory and store the result "
        "in the registry under the key 'task_results/directory_listing'."
    )
    result = await agent.run(test_task)
    print("\n=== Agent Result ===")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())