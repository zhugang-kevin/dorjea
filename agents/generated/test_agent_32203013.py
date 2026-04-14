import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic
from pydantic import BaseModel, Field


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_agent_32203013")


class TaskRecord(BaseModel):
    """Represents a timestamped record of an agent action."""
    
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"


class AgentState(BaseModel):
    """Represents the current state of the agent."""
    
    agent_id: str
    agent_name: str = "test_agent_32203013"
    department: str = "general"
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_task: str = ""
    status: str = "initializing"
    records: list[TaskRecord] = Field(default_factory=list)
    task_outcomes: dict[str, Any] = Field(default_factory=dict)


class CompletionReport(BaseModel):
    """Structured completion report conforming to communication protocol."""
    
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = "test_agent_32203013"
    session_id: str
    task: str
    status: str
    started_at: str
    completed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actions_taken: list[dict[str, Any]] = Field(default_factory=list)
    outcome: str = ""
    errors: list[str] = Field(default_factory=list)
    verification_passed: bool = False


class TestAgent32203013:
    """
    Agent: test_agent_32203013
    Department: general
    
    Mission: Test mission for automated testing. This agent is designed to support
    general department operations and automated testing workflows. It ensures reliable
    execution of assigned tasks within defined parameters.
    
    Responsibilities:
    - Parse and validate all incoming task specifications before initiating any execution step
    - Execute assigned test and operational workflows in strict accordance with the execution_workflow sequence
    - Maintain accurate and timestamped records of all actions taken during a session in filesystem_server
    - Register and update agent state and task outcomes in registry_server throughout the lifecycle
    - Apply all decision_rules consistently at every applicable branch point during execution
    - Perform self-verification after each workflow completion using the verification_logic checklist
    - Emit structured completion reports conforming to the communication_protocol upon task conclusion
    - Escalate unresolvable failures or ambiguities promptly according to escalation_triggers
    """
    
    TOOLS = [
        {
            "name": "filesystem_server",
            "description": (
                "Manages file system operations for the agent. Use this tool to read, write, "
                "list, and delete files. Maintains timestamped records of all actions taken "
                "during a session. Supports operations: read_file, write_file, list_files, "
                "delete_file, append_to_file."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read_file", "write_file", "list_files", "delete_file", "append_to_file"],
                        "description": "The filesystem operation to perform"
                    },
                    "path": {
                        "type": "string",
                        "description": "The file path for the operation"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write or append (required for write_file and append_to_file)"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "registry_server",
            "description": (
                "Manages agent state registration and task outcome tracking. Use this tool to "
                "register agent state, update task outcomes, query registry entries, and manage "
                "the agent lifecycle. Supports operations: register_agent, update_state, "
                "record_outcome, query_registry, deregister_agent."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["register_agent", "update_state", "record_outcome", "query_registry", "deregister_agent"],
                        "description": "The registry operation to perform"
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "The unique identifier for the agent"
                    },
                    "state_data": {
                        "type": "object",
                        "description": "State data to register or update"
                    },
                    "outcome_data": {
                        "type": "object",
                        "description": "Task outcome data to record"
                    },
                    "query_params": {
                        "type": "object",
                        "description": "Parameters for querying the registry"
                    }
                },
                "required": ["operation"]
            }
        }
    ]
    
    def __init__(self):
        """
        Initialize the TestAgent32203013 with configuration from environment variables.
        
        Reads the following environment variables:
        - ANTHROPIC_API_KEY: API key for Anthropic Claude (required)
        - AGENT_ID: Unique identifier for this agent instance (defaults to generated UUID)
        - AGENT_MAX_TOKENS: Maximum tokens for model responses (defaults to 4096)
        - AGENT_MAX_ITERATIONS: Maximum agentic loop iterations (defaults to 10)
        - AGENT_LOG_LEVEL: Logging level (defaults to INFO)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.agent_id = os.getenv("AGENT_ID", str(uuid.uuid4()))
        self.max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        self.max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
        self.model = "claude-sonnet-4-6"
        
        log_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        self.state = AgentState(
            agent_id=self.agent_id,
            agent_name="test_agent_32203013",
            department="general"
        )
        
        self._filesystem_store: dict[str, str] = {}
        self._registry_store: dict[str, Any] = {}
        
        logger.info(f"Agent {self.agent_id} initialized successfully")
    
    def _add_record(self, action: str, details: dict[str, Any], status: str = "completed") -> TaskRecord:
        """
        Add a timestamped record of an action to the agent's session log.
        
        Args:
            action: Description of the action taken
            details: Additional details about the action
            status: Status of the action (pending, completed, failed)
            
        Returns:
            The created TaskRecord instance
        """
        record = TaskRecord(
            action=action,
            details=details,
            status=status
        )
        self.state.records.append(record)
        logger.info(f"Action recorded: {action} [{status}]")
        return record
    
    def _execute_filesystem_server(self, operation: str, path: str = "", content: str = "") -> dict[str, Any]:
        """
        Execute a filesystem server operation.
        
        Simulates filesystem operations including reading, writing, listing,
        deleting, and appending to files. All operations are logged with timestamps.
        
        Args:
            operation: The filesystem operation to perform
            path: The file path for the operation
            content: Content for write/append operations
            
        Returns:
            Dictionary containing operation result and metadata
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if operation == "write_file":
            self._filesystem_store[path] = content
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "bytes_written": len(content),
                "timestamp": timestamp
            }
        elif operation == "read_file":
            if path in self._filesystem_store:
                return {
                    "success": True,
                    "operation": operation,
                    "path": path,
                    "content": self._filesystem_store[path],
                    "timestamp": timestamp
                }
            return {
                "success": False,
                "operation": operation,
                "path": path,
                "error": f"File not found: {path}",
                "timestamp": timestamp
            }
        elif operation == "list_files":
            prefix = path if path else ""
            files = [k for k in self._filesystem_store.keys() if k.startswith(prefix)]
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "files": files,
                "count": len(files),
                "timestamp": timestamp
            }
        elif operation == "delete_file":
            if path in self._filesystem_store:
                del self._filesystem_store[path]
                return {
                    "success": True,
                    "operation": operation,
                    "path": path,
                    "timestamp": timestamp
                }
            return {
                "success": False,
                "operation": operation,
                "path": path,
                "error": f"File not found: {path}",
                "timestamp": timestamp
            }
        elif operation == "append_to_file":
            if path in self._filesystem_store:
                self._filesystem_store[path] += content
            else:
                self._filesystem_store[path] = content
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "bytes_appended": len(content),
                "timestamp": timestamp
            }
        else:
            return {
                "success": False,
                "operation": operation,
                "error": f"Unknown operation: {operation}",
                "timestamp": timestamp
            }
    
    def _execute_registry_server(self, operation: str, agent_id: str = "", 
                                  state_data: dict = None, outcome_data: dict = None,
                                  query_params: dict = None) -> dict[str, Any]:
        """
        Execute a registry server operation.
        
        Manages agent state registration and task outcome tracking in the registry.
        Supports registering agents, updating state, recording outcomes, querying,
        and deregistering agents.
        
        Args:
            operation: The registry operation to perform
            agent_id: The unique identifier for the agent
            state_data: State data to register or update
            outcome_data: Task outcome data to record
            query_params: Parameters for querying the registry
            
        Returns:
            Dictionary containing operation result and metadata
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        target_id = agent_id or self.agent_id
        
        if operation == "register_agent":
            self._registry_store[target_id] = {
                "agent_id": target_id,
                "registered_at": timestamp,
                "state": state_data or {},
                "outcomes": []
            }
            return {
                "success": True,
                "operation": operation,
                "agent_id": target_id,
                "timestamp": timestamp
            }
        elif operation == "update_state":
            if target_id in self._registry_store:
                self._registry_store[target_id]["state"].update(state_data or {})
                self._registry_store[target_id]["last_updated"] = timestamp
                return {
                    "success": True,
                    "operation": operation,
                    "agent_id": target_id,
                    "timestamp": timestamp
                }
            return {
                "success": False,
                "operation": operation,
                "agent_id": target_id,
                "error": f"Agent not registered: {target_id}",
                "timestamp": timestamp
            }
        elif operation == "record_outcome":
            if target_id in self._registry_store:
                outcome_entry = {
                    "timestamp": timestamp,
                    "outcome": outcome_data or {}
                }
                self._registry_store[target_id]["outcomes"].append(outcome_entry)
                return {
                    "success": True,
                    "operation": operation,
                    "agent_id": target_id,
                    "outcome_count": len(self._registry_store[target_id]["outcomes"]),
                    "timestamp": timestamp
                }
            return {
                "success": False,
                "operation": operation,
                "agent_id": target_id,
                "error": f"Agent not registered: {target_id}",
                "timestamp": timestamp
            }
        elif operation == "query_registry":
            params = query_params or {}
            if "agent_id" in params:
                query_id = params["agent_id"]
                if query_id in self._registry_store:
                    return {
                        "success": True,
                        "operation": operation,
                        "result": self._registry_store[query_id],
                        "timestamp": timestamp
                    }
                return {
                    "success": False,
                    "operation": operation,
                    "error": f"Agent not found: {query_id}",
                    "timestamp": timestamp
                }
            return {
                "success": True,
                "operation": operation,
                "result": list(self._registry_store.keys()),
                "count": len(self._registry_store),
                "timestamp": timestamp
            }
        elif operation == "deregister_agent":
            if target_id in self._registry_store:
                del self._registry_store[target_id]
                return {
                    "success": True,
                    "operation": operation,
                    "agent_id": target_id,
                    "timestamp": timestamp
                }
            return {
                "success": False,
                "operation": operation,
                "agent_id": target_id,
                "error": f"Agent not registered: {target_id}",
                "timestamp": timestamp
            }
        else:
            return {
                "success": False,
                "operation": operation,
                "error": f"Unknown operation: {operation}",
                "timestamp": timestamp
            }
    
    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Process a tool call from the model and return the result.
        
        Routes tool calls to the appropriate handler (filesystem_server or registry_server)
        and logs the action with a timestamp.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            
        Returns:
            JSON string containing the tool execution result
        """
        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
        
        try:
            if tool_name == "filesystem_server":
                operation = tool_input.get("operation", "")
                path = tool_input.get("path", "")
                content = tool_input.get("content", "")
                result = self._execute_filesystem_server(operation, path, content)
                
            elif tool_name == "registry_server":
                operation = tool_input.get("operation", "")
                agent_id = tool_input.get("agent_id", "")
                state_data = tool_input.get("state_data", {})
                outcome_data = tool_input.get("outcome_data", {})
                query_params = tool_input.get("query_params", {})
                result = self._execute_registry_server(
                    operation, agent_id, state_data, outcome_data, query_params
                )
            else:
                result = {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            self._add_record(
                action=f"tool_call:{tool_name}:{tool_input.get('operation', 'unknown')}",
                details={"tool": tool_name, "input": tool_input, "result": result},
                status="completed" if result.get("success", False) else "failed"
            )
            
            return json.dumps(result)
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "tool": tool_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self._add_record(
                action=f"tool_call:{tool_name}:error",
                details={"tool": tool_name, "input": tool_input, "error": str(e)},
                status="failed"
            )
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return json.dumps(error_result)
    
    def _validate_task(self, task: str) -> tuple[bool, str]:
        """
        Validate an incoming task specification before execution.
        
        Checks that the task is non-empty, within acceptable length limits,
        and contains meaningful content for processing.
        
        Args:
            task: The task specification string to validate
            
        Returns:
            Tuple of (is_valid: bool, message: str) indicating validation result
        """
        if not task or not task.strip():
            return False, "Task specification cannot be empty"
        
        if len(task) > 10000:
            return False, f"Task specification exceeds maximum length of 10000 characters (got {len(task)})"
        
        if len(task.strip()) < 3:
            return False, "Task specification is too short to be meaningful"
        
        return True, "Task validation passed"
    
    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for the agent.
        
        Constructs a comprehensive system prompt that defines the agent's identity,
        mission, responsibilities, and operational guidelines.
        
        Returns:
            The complete system prompt string
        """
        return """You are test_agent_32203013, an AI agent for the general department.

Mission: Test mission for automated testing. This agent is designed to support general department operations and automated testing workflows. It ensures reliable execution of assigned tasks within defined parameters.

Your responsibilities are:
1. Parse and validate all incoming task specifications before initiating any execution step
2. Execute assigned test and operational workflows in strict accordance with the execution_workflow sequence
3. Maintain accurate and timestamped records of all actions taken during a session in filesystem_server
4. Register and update agent state and task outcomes in registry_server throughout the lifecycle
5. Apply all decision_rules consistently at every applicable branch point during execution
6. Perform self-verification after each workflow completion using the verification_logic checklist
7. Emit structured completion reports conforming to the communication_protocol upon task conclusion
8. Escalate unresolvable failures or ambiguities promptly according to escalation_triggers

Execution Workflow:
1. INITIALIZE: Register yourself in registry_server with your agent_id and initial state
2. VALIDATE: Parse and validate the incoming task specification
3. PLAN: Create an execution plan and write it to filesystem_server
4. EXECUTE: Carry out the task steps, logging each action to filesystem_server
5. UPDATE: Update your state in registry_server after each significant step
6. VERIFY: Perform self-verification by checking all required actions were completed
7. REPORT: Record the final outcome in registry_server and write completion report to filesystem_server
8. COMPLETE: Return a structured completion summary

Decision Rules:
- If a task is ambiguous, make reasonable assumptions and document them
- If a tool call fails, retry once before marking as failed
- Always update registry_server state before and after major operations
- Log all actions to filesystem_server with timestamps
- If verification fails, attempt remediation before escalating

Verification Checklist:
- [ ] Agent registered in registry_server
- [ ] Task validated and documented
- [ ] Execution plan created
- [ ] All task steps executed
- [ ] All actions logged to filesystem_server
- [ ] Registry state updated throughout
- [ ] Completion report written

Communication Protocol:
- All reports must include: agent_id, session_id, task, status, timestamps, actions_taken
- Use structured JSON format for all registry entries
- File paths should follow pattern: /sessions/{session_id}/{filename}

Escalation Triggers:
- Tool unavailable after retry
- Task specification fundamentally invalid
- Critical verification failure that cannot be remediated

Always be thorough, systematic, and maintain complete audit trails of your work."""
    
    def _perform_verification(self) -> tuple[bool, list[str]]:
        """
        Perform self-verification after workflow completion.
        
        Checks the verification logic checklist to ensure all required actions
        were completed during the session.
        
        Returns:
            Tuple of (verification_passed: bool, failed_checks: list[str])
        """
        failed_checks = []
        
        action_types = {record.action for record in self.state.records}
        
        has_registration = any("register_agent" in action for action in action_types)
        if not has_registration:
            failed_checks.append("Agent not registered in registry_server")
        
        has_filesystem_write = any("filesystem_server:write_file" in action or 
                                    "filesystem_server:append_to_file" in action 
                                    for action in action_types)
        if not has_filesystem_write:
            failed_checks.append("No actions logged to filesystem_server")
        
        has_registry_update = any("registry_server:update_state" in action or 
                                   "registry_server:record_outcome" in action 
                                   for action in action_types)
        if not has_registry_update:
            failed_checks.append("Registry state not updated during execution")
        
        verification_passed = len(failed_checks) == 0
        return verification_passed, failed_checks
    
    async def run(self, task: str) -> str:
        """
        Execute the agent's main task processing loop.
        
        Validates the incoming task, initializes the agent state, runs the agentic
        loop with tool use, performs verification, and returns a structured completion
        report.
        
        Args:
            task: The task specification string to execute
            
        Returns:
            JSON string containing the structured completion report
            
        Raises:
            ValueError: If the task fails validation
        """
        logger.info(f"Agent {self.agent_id} starting task execution")
        
        is_valid, validation_message = self._validate_task(task)
        if not is_valid:
            error_report = CompletionReport(
                session_id=self.state.session_id,
                task=task,
                status="failed",
                started_at=self.state.started_at,
                outcome=f"Task validation failed: {validation_message}",
                errors=[validation_message],
                verification_passed=False
            )
            return error_report.model_dump_json(indent=2)
        
        self._add_record(
            action="task_validation",
            details={"task": task[:200], "result": validation_message},
            status="completed"
        )
        
        self.state.current_task = task
        self.state.status = "running"
        
        messages = [
            {
                "role": "user",
                "content": f"Execute the following task: {task}\n\nYour agent_id is: {self.agent_id}\nYour session_id is: {self.state.session_id}\n\nFollow your execution workflow completely."
            }
        ]
        
        errors = []
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Agentic loop iteration {iteration}/{self.max_iterations}")
            
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self._build_system_prompt(),
                    tools=self.TOOLS,
                    messages=messages
                )
            except anthropic.APIConnectionError as e:
                error_msg = f"API connection error on iteration {iteration}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                break
            except anthropic.RateLimitError as e:
                error_msg = f"Rate limit error on iteration {iteration}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                break
            except anthropic.APIStatusError as e:
                error_msg = f"API status error on iteration {iteration}: {e.status_code} - {e.message}"
                logger.error(error_msg)
                errors.append(error_msg)
                break
            except Exception as e:
                error_msg = f"Unexpected error on iteration {iteration}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                break
            
            messages.append({"role": "assistant", "content": response.content})
            
            if response.stop_reason == "end_turn":
                logger.info("Model completed task (end_turn)")
                break
            
            if response.stop_reason == "tool_use":
                tool_results = []
                
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = self._process_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result
                        })
                
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                else:
                    logger.warning("Tool use stop reason but no tool calls found")
                    break
            else:
                logger.info(f"Unexpected stop reason: {response.stop_reason}")
                break
        
        if iteration >= self.max_iterations:
            logger.warning(f"Reached maximum iterations ({self.max_iterations})")
            errors.append(f"Reached maximum iterations limit of {self.max_iterations}")
        
        verification_passed, failed_checks = self._perform_verification()
        
        if not verification_passed:
            logger.warning(f"Verification failed: {failed_checks}")
            errors.extend([f"Verification failed: {check}" for check in failed_checks])
        
        final_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "type") and block.type == "text":
                            final_text = block.text
                            break
                elif isinstance(content, str):
                    final_text = content
                if final_text:
                    break
        
        actions_taken = [
            {
                "record_id": record.record_id,
                "timestamp": record.timestamp,
                "action": record.action,
                "status": record.status
            }
            for record in self.state.records
        ]
        
        overall_status = "completed" if not errors else "completed_with_errors"
        if iteration >= self.max_iterations and errors:
            overall_status = "failed"
        
        completion_report = CompletionReport(
            session_id=self.state.session_id,
            task=task,
            status=overall_status,
            started_at=self.state.started_at,
            actions_taken=actions_taken,
            outcome=final_text[:1000] if final_text else "Task execution completed",
            errors=errors,
            verification_passed=verification_passed
        )
        
        self.state.status = overall_status
        self.state.task_outcomes[self.state.session_id] = {
            "status": overall_status,
            "verification_passed": verification_passed,
            "error_count": len(errors)
        }
        
        logger.info(f"Agent {self.agent_id} completed task with status: {overall_status}")
        
        return completion_report.model_dump_json(indent=2)


async def main():
    """
    Main entry point for running the TestAgent32203013.
    
    Reads the task from the AGENT_TASK environment variable and executes it.
    Falls back to a default test task if no task is specified.
    """
    task = os.getenv("AGENT_TASK", "Perform a system health check and log the results")
    
    try:
        agent = TestAgent32203013()
        result = await agent.run(task)
        print(result)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error running agent: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())