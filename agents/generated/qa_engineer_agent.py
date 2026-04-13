"""
QA Engineer Agent - Designs and executes comprehensive pytest test suites
to validate software outputs against defined acceptance criteria.
"""

import json
import os
import re
from datetime import datetime
from typing import Any

import anthropic


class QaEngineerAgent:
    """
    QA Engineer Agent that designs and writes comprehensive pytest test suites,
    identifies edge cases, executes regression tests, and provides actionable
    diagnostic reports to ensure production-ready code quality.
    """

    def __init__(self):
        """
        Initialize the QA Engineer Agent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            GITHUB_PERSONAL_ACCESS_TOKEN: GitHub personal access token for repository access
            QA_AGENT_MODEL: Model to use (defaults to claude-sonnet-4-6)
            QA_AGENT_MAX_TOKENS: Maximum tokens for responses (defaults to 8096)
            QA_AGENT_MAX_ITERATIONS: Maximum tool call iterations (defaults to 50)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
        self.model = os.getenv("QA_AGENT_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("QA_AGENT_MAX_TOKENS", "8096"))
        self.max_iterations = int(os.getenv("QA_AGENT_MAX_ITERATIONS", "50"))

        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.mcp_servers = self._build_mcp_servers()

        self.system_prompt = """You are a QA Engineer Agent specializing in designing and executing comprehensive pytest test suites.

Your mission is to serve as the final quality gate, ensuring every deliverable meets quality standards before release.

Core Responsibilities:
1. Design and implement comprehensive pytest test suites covering unit, integration, and functional test scenarios based on acceptance criteria
2. Identify and document edge cases, boundary conditions, and negative test scenarios for all features under test
3. Execute regression test suites to detect unintended side effects or regressions introduced by new code changes
4. Analyze test failures and produce actionable diagnostic reports including root cause analysis, affected components, and suggested fixes
5. Maintain and update existing test suites to reflect changes in requirements, APIs, or system behavior
6. Validate software outputs against defined acceptance criteria and flag any deviations with severity classifications
7. Organize test artifacts and results in the repository using consistent naming conventions and structured reporting
8. Review code changes via GitHub to assess testability and identify gaps in test coverage

Testing Standards:
- Write pytest tests following AAA pattern (Arrange, Act, Assert)
- Use descriptive test names that explain what is being tested and expected behavior
- Include docstrings for all test classes and methods
- Use pytest fixtures for reusable test setup and teardown
- Implement parametrize decorators for data-driven tests
- Add proper markers (unit, integration, functional, regression, smoke)
- Ensure tests are isolated, deterministic, and independent
- Use mocking appropriately to isolate units under test
- Include both positive and negative test cases
- Document severity levels: CRITICAL, HIGH, MEDIUM, LOW

Diagnostic Report Format:
When reporting test failures, always include:
- Test name and location
- Failure type and error message
- Root cause analysis
- Affected components
- Severity classification
- Suggested fix with code example when applicable
- Regression risk assessment

File Organization:
- tests/unit/ for unit tests
- tests/integration/ for integration tests
- tests/functional/ for functional/e2e tests
- tests/regression/ for regression test suites
- tests/conftest.py for shared fixtures
- tests/reports/ for test result artifacts

Always provide complete, runnable pytest code without placeholders or TODO comments."""

    def _build_mcp_servers(self) -> list[dict[str, Any]]:
        """
        Build the MCP server configurations for filesystem and GitHub tools.

        Returns:
            List of MCP server configuration dictionaries.
        """
        servers = []

        filesystem_server = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", os.getcwd()],
            "env": {}
        }
        servers.append(filesystem_server)

        if self.github_token:
            github_server = {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": self.github_token
                }
            }
            servers.append(github_server)

        return servers

    def _get_current_timestamp(self) -> str:
        """
        Get the current timestamp formatted for reports and file naming.

        Returns:
            Formatted timestamp string.
        """
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _format_task_context(self, task: str) -> str:
        """
        Format the task with additional context for the agent.

        Args:
            task: The raw task description from the caller.

        Returns:
            Enhanced task description with context and instructions.
        """
        timestamp = self._get_current_timestamp()
        return f"""Task received at {timestamp}:

{task}

Please approach this task systematically:
1. First, understand the requirements and acceptance criteria
2. Explore the codebase structure if needed using filesystem tools
3. Review any relevant GitHub issues, PRs, or code changes if applicable
4. Design a comprehensive test strategy
5. Implement complete, runnable pytest tests
6. Organize tests according to the established directory structure
7. Provide a summary of test coverage and any identified gaps or risks

Ensure all test code is complete, well-documented, and follows pytest best practices."""

    async def run(self, task: str) -> str:
        """
        Execute the QA engineering task using Claude with MCP tool access.

        This method runs an agentic loop where Claude can use filesystem and GitHub
        tools to explore codebases, read requirements, write test files, and analyze
        code changes to produce comprehensive test suites and quality reports.

        Args:
            task: Description of the QA task to perform, such as writing tests for
                  a specific feature, running regression analysis, or reviewing
                  code changes for testability.

        Returns:
            String containing the agent's final response, including test implementations,
            diagnostic reports, coverage analysis, or quality assessments.

        Raises:
            anthropic.APIError: If there's an error communicating with the Anthropic API.
            ValueError: If required configuration is missing.
        """
        formatted_task = self._format_task_context(task)
        messages = [{"role": "user", "content": formatted_task}]

        iteration_count = 0
        final_response = ""

        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
                betas=["mcp-client-2025-04-04"],
                mcp_servers=self.mcp_servers,
            ) as stream:
                response = stream.get_final_message()

        except anthropic.APIConnectionError as e:
            return f"Connection error communicating with Anthropic API: {str(e)}"
        except anthropic.RateLimitError as e:
            return f"Rate limit exceeded. Please retry after a moment: {str(e)}"
        except anthropic.APIStatusError as e:
            return f"API error (status {e.status_code}): {str(e)}"
        except Exception as e:
            return f"Unexpected error during initial API call: {str(e)}"

        while iteration_count < self.max_iterations:
            iteration_count += 1

            stop_reason = response.stop_reason

            if stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response = block.text
                        break
                break

            if stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"status": "processed", "tool": block.name})
                        }
                        tool_results.append(tool_result)

                if not tool_results:
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response = block.text
                            break
                    break

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                try:
                    with self.client.beta.messages.stream(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=self.system_prompt,
                        messages=messages,
                        betas=["mcp-client-2025-04-04"],
                        mcp_servers=self.mcp_servers,
                    ) as stream:
                        response = stream.get_final_message()

                except anthropic.APIConnectionError as e:
                    return f"Connection error during tool execution loop: {str(e)}"
                except anthropic.RateLimitError as e:
                    return f"Rate limit exceeded during tool execution: {str(e)}"
                except anthropic.APIStatusError as e:
                    return f"API error during tool execution (status {e.status_code}): {str(e)}"
                except Exception as e:
                    return f"Unexpected error during tool execution loop: {str(e)}"

            elif stop_reason in ("max_tokens", "stop_sequence"):
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response = block.text
                        break
                if stop_reason == "max_tokens":
                    final_response += "\n\n[Note: Response was truncated due to token limit. Consider breaking the task into smaller subtasks.]"
                break

            else:
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response = block.text
                        break
                break

        if iteration_count >= self.max_iterations and not final_response:
            final_response = f"Maximum iteration limit ({self.max_iterations}) reached. The task may require breaking into smaller subtasks for complete execution."

        if not final_response:
            try:
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response = block.text
                        break
            except Exception:
                final_response = "Task completed but no text response was generated."

        return final_response


async def main():
    """
    Main entry point for testing the QA Engineer Agent directly.
    """
    agent = QaEngineerAgent()

    test_task = """
    Please create a comprehensive pytest test suite for a simple user authentication module.
    
    The module has the following functions:
    - validate_email(email: str) -> bool: Returns True if email format is valid
    - hash_password(password: str) -> str: Returns bcrypt hash of password
    - verify_password(password: str, hashed: str) -> bool: Verifies password against hash
    - create_user(username: str, email: str, password: str) -> dict: Creates user record
    - authenticate_user(username: str, password: str) -> Optional[dict]: Returns user if auth succeeds
    
    Acceptance Criteria:
    - Email validation must reject malformed emails
    - Passwords must be at least 8 characters
    - Authentication must fail with wrong credentials
    - User creation must fail with duplicate usernames
    
    Please write complete pytest tests covering all acceptance criteria, edge cases, and failure scenarios.
    """

    print("Starting QA Engineer Agent...")
    print("=" * 60)

    result = await agent.run(test_task)

    print("Agent Response:")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())