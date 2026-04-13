"""
Backend Developer Agent

A production-ready AI agent for designing and implementing FastAPI endpoints
with robust error handling, structured logging, and comprehensive test coverage.
"""

import json
import logging
import os
import sys
from typing import Any

import anthropic
from pydantic import BaseModel, Field


# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("backend_developer_agent")


class AgentConfig(BaseModel):
    """Configuration model for the Backend Developer Agent."""

    model: str = Field(default="claude-sonnet-4-6", description="Anthropic model to use")
    max_tokens: int = Field(default=8096, description="Maximum tokens for response")
    api_key: str = Field(description="Anthropic API key")
    department: str = Field(default="engineering", description="Department this agent belongs to")
    agent_name: str = Field(default="backend_developer_agent", description="Name of this agent")


class ToolResult(BaseModel):
    """Model representing a tool execution result."""

    tool_name: str
    tool_use_id: str
    content: str
    is_error: bool = False


class BackendDeveloperAgent:
    """
    Backend Developer Agent for designing and implementing production-ready FastAPI endpoints.

    This agent leverages Claude AI to assist with:
    - Designing RESTful API endpoints following OpenAPI standards
    - Implementing robust error handling with appropriate HTTP status codes
    - Setting up structured logging for production observability
    - Writing comprehensive unit and integration tests using pytest
    - Defining and validating request/response schemas using Pydantic
    - Optimizing API performance through async patterns and caching
    - Documenting API endpoints with OpenAPI metadata
    - Reviewing and refactoring existing backend code
    """

    def __init__(self) -> None:
        """
        Initialize the Backend Developer Agent.

        Reads all configuration from environment variables:
        - ANTHROPIC_API_KEY: Required. The Anthropic API key for authentication.
        - AGENT_MODEL: Optional. The Claude model to use (default: claude-sonnet-4-6).
        - AGENT_MAX_TOKENS: Optional. Maximum tokens for responses (default: 8096).
        - AGENT_DEPARTMENT: Optional. Department identifier (default: engineering).
        - AGENT_NAME: Optional. Agent name identifier (default: backend_developer_agent).

        Raises:
            ValueError: If ANTHROPIC_API_KEY environment variable is not set.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.config = AgentConfig(
            api_key=api_key,
            model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8096")),
            department=os.getenv("AGENT_DEPARTMENT", "engineering"),
            agent_name=os.getenv("AGENT_NAME", "backend_developer_agent"),
        )

        self.client = anthropic.Anthropic(api_key=self.config.api_key)

        self.tools = self._define_tools()

        self.system_prompt = self._build_system_prompt()

        logger.info(
            f"BackendDeveloperAgent initialized with model={self.config.model}, "
            f"department={self.config.department}"
        )

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for the Backend Developer Agent.

        Returns:
            str: The complete system prompt defining agent behavior and expertise.
        """
        return """You are an expert Backend Developer Agent specializing in Python and FastAPI development.

Your mission is to design and implement production-ready FastAPI endpoints with robust error handling,
structured logging, and comprehensive test coverage. You ensure all API code follows best practices
for performance, security, and maintainability.

Your core responsibilities include:

1. **API Design & Implementation**: Design RESTful API endpoints following OpenAPI specification
   standards. Implement clean, well-structured FastAPI routes with proper HTTP methods, status codes,
   and response models.

2. **Error Handling**: Implement robust error handling with appropriate HTTP status codes (400, 401,
   403, 404, 422, 500, etc.), structured error responses using consistent JSON schemas, and
   meaningful error messages that aid debugging without exposing sensitive information.

3. **Structured Logging**: Set up production-grade logging using Python's logging framework with
   structured JSON output, correlation IDs, request/response logging middleware, and appropriate
   log levels for different environments.

4. **Testing**: Write comprehensive pytest test suites including unit tests for business logic,
   integration tests for API endpoints using TestClient, fixtures for database and service mocking,
   and parametrized tests for edge cases. Aim for >90% code coverage.

5. **Schema Validation**: Define strict Pydantic models for all request/response schemas with
   proper field validation, custom validators, and clear field descriptions for OpenAPI docs.

6. **Performance Optimization**: Implement async/await patterns throughout, connection pooling
   for databases, Redis caching for frequently accessed data, and efficient query design.

7. **Documentation**: Document all endpoints with comprehensive docstrings, OpenAPI metadata
   including tags, summaries, descriptions, request/response examples, and error responses.

8. **Code Review & Refactoring**: Review existing code for technical debt, apply SOLID principles,
   improve type annotations, and align with current FastAPI and Python best practices.

When using tools:
- Use filesystem_server to read, write, and manage code files
- Use github_server to review PRs, create branches, and manage code repositories
- Use web_search to look up latest FastAPI documentation, security advisories, and best practices

Always produce complete, production-ready code with no placeholders or TODO comments.
Follow PEP 8 style guidelines and use type hints throughout."""

    def _define_tools(self) -> list[dict[str, Any]]:
        """
        Define the tools available to the Backend Developer Agent.

        Returns:
            list[dict[str, Any]]: List of tool definitions in Anthropic's tool format.
        """
        return [
            {
                "name": "filesystem_server",
                "description": (
                    "Interact with the local filesystem to read, write, create, and manage files "
                    "and directories. Use this to read existing code files, write new implementations, "
                    "create test files, and manage project structure."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list", "create_dir", "delete", "exists"],
                            "description": "The filesystem operation to perform"
                        },
                        "path": {
                            "type": "string",
                            "description": "The file or directory path to operate on"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to file (required for write operation)"
                        }
                    },
                    "required": ["operation", "path"]
                }
            },
            {
                "name": "github_server",
                "description": (
                    "Interact with GitHub repositories to manage code, review pull requests, "
                    "create branches, commit changes, and collaborate with engineering teams. "
                    "Use this to review existing code, create feature branches, and manage PRs."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["get_repo", "list_files", "get_file", "create_branch",
                                     "commit_file", "create_pr", "list_prs", "review_pr"],
                            "description": "The GitHub operation to perform"
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository in format 'owner/repo'"
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name for branch operations"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to file within repository"
                        },
                        "content": {
                            "type": "string",
                            "description": "File content for commit operations"
                        },
                        "message": {
                            "type": "string",
                            "description": "Commit message or PR description"
                        },
                        "pr_number": {
                            "type": "integer",
                            "description": "Pull request number for PR operations"
                        }
                    },
                    "required": ["operation"]
                }
            },
            {
                "name": "web_search",
                "description": (
                    "Search the web for current information about FastAPI, Python best practices, "
                    "security advisories, library documentation, and technical solutions. "
                    "Use this to find up-to-date documentation and community solutions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to execute"
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any], tool_use_id: str) -> ToolResult:
        """
        Execute a tool call and return the result.

        This method handles the execution of tools requested by the Claude model.
        In a production environment, these would connect to actual services.
        Currently implements simulation logic for demonstration purposes.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Dictionary of input parameters for the tool.
            tool_use_id: Unique identifier for this tool use instance.

        Returns:
            ToolResult: The result of the tool execution.
        """
        logger.info(f"Executing tool: {tool_name} with input keys: {list(tool_input.keys())}")

        try:
            if tool_name == "filesystem_server":
                return self._execute_filesystem_tool(tool_input, tool_use_id)
            elif tool_name == "github_server":
                return self._execute_github_tool(tool_input, tool_use_id)
            elif tool_name == "web_search":
                return self._execute_web_search_tool(tool_input, tool_use_id)
            else:
                return ToolResult(
                    tool_name=tool_name,
                    tool_use_id=tool_use_id,
                    content=f"Unknown tool: {tool_name}",
                    is_error=True
                )
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {str(e)}")
            return ToolResult(
                tool_name=tool_name,
                tool_use_id=tool_use_id,
                content=f"Tool execution failed: {str(e)}",
                is_error=True
            )

    def _execute_filesystem_tool(self, tool_input: dict[str, Any], tool_use_id: str) -> ToolResult:
        """
        Execute filesystem operations.

        Handles file read, write, list, create_dir, delete, and exists operations
        on the local filesystem.

        Args:
            tool_input: Dictionary containing 'operation', 'path', and optionally 'content'.
            tool_use_id: Unique identifier for this tool use instance.

        Returns:
            ToolResult: Result of the filesystem operation.
        """
        operation = tool_input.get("operation")
        path = tool_input.get("path", "")
        content = tool_input.get("content", "")

        try:
            if operation == "read":
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    return ToolResult(
                        tool_name="filesystem_server",
                        tool_use_id=tool_use_id,
                        content=file_content
                    )
                else:
                    return ToolResult(
                        tool_name="filesystem_server",
                        tool_use_id=tool_use_id,
                        content=f"File not found: {path}",
                        is_error=True
                    )

            elif operation == "write":
                os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return ToolResult(
                    tool_name="filesystem_server",
                    tool_use_id=tool_use_id,
                    content=f"Successfully wrote {len(content)} bytes to {path}"
                )

            elif operation == "list":
                if os.path.exists(path):
                    items = os.listdir(path)
                    return ToolResult(
                        tool_name="filesystem_server",
                        tool_use_id=tool_use_id,
                        content=json.dumps(items)
                    )
                else:
                    return ToolResult(
                        tool_name="filesystem_server",
                        tool_use_id=tool_use_id,
                        content=f"Directory not found: {path}",
                        is_error=True
                    )

            elif operation == "create_dir":
                os.makedirs(path, exist_ok=True)
                return ToolResult(
                    tool_name="filesystem_server",
                    tool_use_id=tool_use_id,
                    content=f"Directory created: {path}"
                )

            elif operation == "exists":
                exists = os.path.exists(path)
                return ToolResult(
                    tool_name="filesystem_server",
                    tool_use_id=tool_use_id,
                    content=json.dumps({"exists": exists, "path": path})
                )

            elif operation == "delete":
                if os.path.exists(path):
                    if os.path.isfile(path):
                        os.remove(path)
                    else:
                        import shutil
                        shutil.rmtree(path)
                    return ToolResult(
                        tool_name="filesystem_server",
                        tool_use_id=tool_use_id,
                        content=f"Successfully deleted: {path}"
                    )
                else:
                    return ToolResult(
                        tool_name="filesystem_server",
                        tool_use_id=tool_use_id,
                        content=f"Path not found: {path}",
                        is_error=True
                    )

            else:
                return ToolResult(
                    tool_name="filesystem_server",
                    tool_use_id=tool_use_id,
                    content=f"Unknown filesystem operation: {operation}",
                    is_error=True
                )

        except PermissionError as e:
            return ToolResult(
                tool_name="filesystem_server",
                tool_use_id=tool_use_id,
                content=f"Permission denied: {str(e)}",
                is_error=True
            )
        except OSError as e:
            return ToolResult(
                tool_name="filesystem_server",
                tool_use_id=tool_use_id,
                content=f"OS error: {str(e)}",
                is_error=True
            )

    def _execute_github_tool(self, tool_input: dict[str, Any], tool_use_id: str) -> ToolResult:
        """
        Execute GitHub repository operations.

        Simulates GitHub API interactions for repository management, code review,
        and collaboration workflows. In production, this would use the GitHub API.

        Args:
            tool_input: Dictionary containing GitHub operation parameters.
            tool_use_id: Unique identifier for this tool use instance.

        Returns:
            ToolResult: Result of the GitHub operation.
        """
        operation = tool_input.get("operation")
        repo = tool_input.get("repo", "")
        branch = tool_input.get("branch", "main")
        file_path = tool_input.get("file_path", "")
        message = tool_input.get("message", "")

        github_token = os.getenv("GITHUB_TOKEN")

        if not github_token:
            logger.warning("GITHUB_TOKEN not set, GitHub operations will be simulated")
            return ToolResult(
                tool_name="github_server",
                tool_use_id=tool_use_id,
                content=json.dumps({
                    "status": "simulated",
                    "operation": operation,
                    "repo": repo,
                    "message": "GitHub operation simulated - GITHUB_TOKEN not configured",
                    "branch": branch,
                    "file_path": file_path
                })
            )

        # In production, implement actual GitHub API calls here
        result = {
            "status": "success",
            "operation": operation,
            "repo": repo,
            "branch": branch,
            "message": message or f"Completed {operation} operation on {repo}"
        }

        return ToolResult(
            tool_name="github_server",
            tool_use_id=tool_use_id,
            content=json.dumps(result)
        )

    def _execute_web_search_tool(self, tool_input: dict[str, Any], tool_use_id: str) -> ToolResult:
        """
        Execute web search operations.

        Performs web searches to find current documentation, best practices,
        and technical solutions. Returns structured search results.

        Args:
            tool_input: Dictionary containing 'query' and optionally 'num_results'.
            tool_use_id: Unique identifier for this tool use instance.

        Returns:
            ToolResult: Search results in structured format.
        """
        query = tool_input.get("query", "")
        num_results = tool_input.get("num_results", 5)

        logger.info(f"Web search query: {query}, num_results: {num_results}")

        # Simulate web search results with relevant FastAPI/Python content
        simulated_results = {
            "query": query,
            "num_results": num_results,
            "results": [
                {
                    "title": f"FastAPI Documentation - {query}",
                    "url": "https://fastapi.tiangolo.com/",
                    "snippet": (
                        "FastAPI is a modern, fast web framework for building APIs with Python 3.8+ "
                        "based on standard Python type hints. Key features include automatic API docs, "
                        "data validation, serialization, and async support."
                    )
                },
                {
                    "title": f"Python Best Practices for {query}",
                    "url": "https://docs.python.org/3/",
                    "snippet": (
                        "Python official documentation covering best practices for async programming, "
                        "error handling, logging, and testing with pytest."
                    )
                },
                {
                    "title": f"Pydantic V2 Documentation - {query}",
                    "url": "https://docs.pydantic.dev/",
                    "snippet": (
                        "Pydantic V2 provides data validation using Python type annotations. "
                        "Features include model validators, field validators, and JSON schema generation."
                    )
                }
            ],
            "note": "Search results are simulated. Configure a search API for production use."
        }

        return ToolResult(
            tool_name="web_search",
            tool_use_id=tool_use_id,
            content=json.dumps(simulated_results, indent=2)
        )

    async def run(self, task: str) -> str:
        """
        Execute a backend development task using the AI agent.

        This method implements an agentic loop that:
        1. Sends the task to Claude with available tools
        2. Processes tool calls requested by the model
        3. Returns tool results to continue the conversation
        4. Repeats until the model provides a final response

        Args:
            task: The backend development task to execute. Can include requests for
                  API design, code implementation, test writing, code review, etc.

        Returns:
            str: The agent's complete response including any generated code,
                 analysis, recommendations, or implementation details.

        Raises:
            anthropic.APIConnectionError: If unable to connect to Anthropic API.
            anthropic.AuthenticationError: If the API key is invalid.
            anthropic.RateLimitError: If API rate limits are exceeded.
        """
        logger.info(f"Starting task execution: {task[:100]}...")

        messages = [
            {
                "role": "user",
                "content": task
            }
        ]

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Agent iteration {iteration}/{max_iterations}")

            try:
                response = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=messages
                )
            except anthropic.APIConnectionError as e:
                logger.error(f"API connection error: {str(e)}")
                raise
            except anthropic.AuthenticationError as e:
                logger.error(f"Authentication error: {str(e)}")
                raise
            except anthropic.RateLimitError as e:
                logger.error(f"Rate limit exceeded: {str(e)}")
                raise
            except anthropic.APIError as e:
                logger.error(f"Anthropic API error: {str(e)}")
                raise

            logger.info(f"Response stop reason: {response.stop_reason}")

            # Check if we have a final response
            if response.stop_reason == "end_turn":
                final_response = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response += block.text

                logger.info(f"Task completed successfully after {iteration} iterations")
                return final_response

            # Process tool calls if stop reason is tool_use
            if response.stop_reason == "tool_use":
                # Add assistant's response to messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Process each tool use block
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"Processing tool call: {block.name} (id: {block.id})")

                        tool_result = self._execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            tool_use_id=block.id
                        )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_result.tool_use_id,
                            "content": tool_result.content,
                            "is_error": tool_result.is_error
                        })

                        if tool_result.is_error:
                            logger.warning(
                                f"Tool {block.name} returned error: {tool_result.content[:200]}"
                            )
                        else:
                            logger.info(
                                f"Tool {block.name} completed successfully"
                            )

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

            else:
                # Unexpected stop reason - extract any text and return
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                final_response = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response += block.text

                if final_response:
                    return final_response
                else:
                    return f"Agent stopped with reason: {response.stop_reason}"

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached without final response")
        return (
            f"Task processing reached maximum iterations ({max_iterations}). "
            "The task may require breaking into smaller subtasks for complete execution."
        )


async def main() -> None:
    """
    Main entry point for running the Backend Developer Agent.

    Demonstrates the agent's capabilities by executing a sample backend
    development task. Configure via environment variables before running.
    """
    try:
        agent = BackendDeveloperAgent()

        sample_task = """
        Design and implement a production-ready FastAPI endpoint for a user management system.
        
        Requirements:
        1. Create a POST /users endpoint that accepts user registration data
        2. Implement proper Pydantic models for request/response validation
        3. Add comprehensive error handling with appropriate HTTP status codes
        4. Set up structured logging for the endpoint
        5. Write pytest tests covering success and error scenarios
        6. Include OpenAPI documentation with examples
        
        The user model should include: email, username, full_name, and password fields.
        Password should be validated for minimum length and complexity.
        Email should be validated for proper format.
        Return appropriate error messages for validation failures.
        """

        logger.info("Starting Backend Developer Agent")
        result = await agent.run(sample_task)

        print("\n" + "="*80)
        print("BACKEND DEVELOPER AGENT RESULT:")
        print("="*80)
        print(result)
        print("="*80 + "\n")

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except anthropic.AuthenticationError:
        logger.error("Invalid Anthropic API key. Please check ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    except anthropic.APIConnectionError:
        logger.error("Failed to connect to Anthropic API. Please check your network connection.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())