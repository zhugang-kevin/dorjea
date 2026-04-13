import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FinanceMonitorAgent:
    """
    Finance Monitor Agent that continuously monitors organizational budgets,
    tracks spending across departments, generates expense summaries, and
    flags anomalous spending patterns.
    """

    def __init__(self):
        """
        Initialize the FinanceMonitorAgent with configuration from environment variables.
        Sets up the Anthropic client, MCP servers, and agent parameters.
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = os.getenv("FINANCE_AGENT_MODEL", "claude-sonnet-4-6")
        self.department = os.getenv("FINANCE_AGENT_DEPARTMENT", "finance")
        self.max_tokens = int(os.getenv("FINANCE_AGENT_MAX_TOKENS", "8096"))
        self.max_iterations = int(os.getenv("FINANCE_AGENT_MAX_ITERATIONS", "10"))

        # MCP Server configurations
        self.filesystem_server_path = os.getenv("FILESYSTEM_SERVER_PATH", "/usr/local/bin/filesystem-server")
        self.filesystem_allowed_dirs = os.getenv("FILESYSTEM_ALLOWED_DIRS", "/tmp/finance").split(",")

        self.registry_server_url = os.getenv("REGISTRY_SERVER_URL", "http://localhost:3001")
        self.registry_server_token = os.getenv("REGISTRY_SERVER_TOKEN", "")

        self.email_server_host = os.getenv("EMAIL_SERVER_HOST", "localhost")
        self.email_server_port = int(os.getenv("EMAIL_SERVER_PORT", "587"))
        self.email_server_user = os.getenv("EMAIL_SERVER_USER", "")
        self.email_server_password = os.getenv("EMAIL_SERVER_PASSWORD", "")
        self.email_from_address = os.getenv("EMAIL_FROM_ADDRESS", "finance-agent@company.com")

        self.calendar_server_url = os.getenv("CALENDAR_SERVER_URL", "http://localhost:3002")
        self.calendar_server_token = os.getenv("CALENDAR_SERVER_TOKEN", "")

        # Alert thresholds
        self.budget_warning_threshold = float(os.getenv("BUDGET_WARNING_THRESHOLD", "0.80"))
        self.budget_critical_threshold = float(os.getenv("BUDGET_CRITICAL_THRESHOLD", "0.95"))
        self.anomaly_std_dev_threshold = float(os.getenv("ANOMALY_STD_DEV_THRESHOLD", "2.0"))

        # Finance leadership contacts
        self.finance_leadership_emails = os.getenv(
            "FINANCE_LEADERSHIP_EMAILS", "cfo@company.com,finance-director@company.com"
        ).split(",")

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for the finance monitor agent.

        Returns:
            str: The complete system prompt defining agent behavior and responsibilities.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"""You are the Finance Monitor Agent for the {self.department} department, operating as of {current_date}.

Your mission is to continuously monitor organizational budgets and track spending across all departments to ensure financial discipline and transparency.

## Core Responsibilities:
1. Monitor budget allocations and actual spending across all departments on a continuous basis
2. Generate comprehensive monthly expense summary reports with department-level breakdowns and trend analysis
3. Identify and flag unusual or anomalous spending patterns that deviate significantly from historical baselines or approved budgets
4. Send automated email alerts to department heads and finance leadership when spending thresholds are approached or exceeded
5. Maintain and update expense tracking records in the filesystem with accurate, timestamped financial data
6. Cross-reference calendar events with expense spikes to correlate spending anomalies with organizational activities
7. Query the registry server to validate vendor and cost-center information against approved financial records
8. Escalate critical budget overruns or suspicious financial activity to the appropriate stakeholders with supporting evidence

## Alert Thresholds:
- Warning threshold: {self.budget_warning_threshold * 100:.0f}% of budget consumed
- Critical threshold: {self.budget_critical_threshold * 100:.0f}% of budget consumed
- Anomaly detection: spending deviating more than {self.anomaly_std_dev_threshold} standard deviations from baseline

## Finance Leadership Contacts:
{', '.join(self.finance_leadership_emails)}

## Operational Guidelines:
- Always timestamp financial records when writing to filesystem
- Validate vendor information against the registry before processing expenses
- Cross-reference unusual spending with calendar events to identify legitimate causes
- Provide clear, evidence-based justifications when escalating issues
- Maintain audit trails for all financial monitoring activities
- Use structured JSON format for all financial data stored in filesystem
- Generate reports in both human-readable and machine-parseable formats

## Data Integrity:
- Never modify historical financial records; only append new data
- Always verify data consistency before generating reports
- Flag any data discrepancies for manual review
- Maintain separate logs for monitoring activities vs. financial data

When executing tasks, use the available tools systematically:
1. Use filesystem_server to read/write financial data and reports
2. Use registry_server to validate vendors and cost centers
3. Use email to send alerts and reports to stakeholders
4. Use calendar to correlate spending patterns with organizational events

Always provide detailed, actionable insights in your responses."""

    def _get_mcp_servers(self) -> list[dict[str, Any]]:
        """
        Build the MCP server configurations for all allowed tools.

        Returns:
            list[dict]: List of MCP server configuration dictionaries.
        """
        servers = []

        # Filesystem server
        filesystem_server = {
            "type": "stdio",
            "command": self.filesystem_server_path,
            "args": self.filesystem_allowed_dirs,
            "env": {
                "NODE_ENV": "production"
            }
        }
        servers.append(filesystem_server)

        # Registry server
        if self.registry_server_url:
            registry_server = {
                "type": "sse",
                "url": f"{self.registry_server_url}/sse",
                "headers": {
                    "Authorization": f"Bearer {self.registry_server_token}"
                } if self.registry_server_token else {}
            }
            servers.append(registry_server)

        # Email server (SMTP MCP)
        email_server = {
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-email",
                "--host", self.email_server_host,
                "--port", str(self.email_server_port),
                "--user", self.email_server_user,
                "--from", self.email_from_address
            ],
            "env": {
                "EMAIL_PASSWORD": self.email_server_password
            }
        }
        servers.append(email_server)

        # Calendar server
        if self.calendar_server_url:
            calendar_server = {
                "type": "sse",
                "url": f"{self.calendar_server_url}/sse",
                "headers": {
                    "Authorization": f"Bearer {self.calendar_server_token}"
                } if self.calendar_server_token else {}
            }
            servers.append(calendar_server)

        return servers

    async def run(self, task: str) -> str:
        """
        Execute a finance monitoring task using the agent with MCP tools.

        This method runs an agentic loop that processes the given task using
        Claude claude-sonnet-4-6 with access to filesystem, registry, email, and calendar
        tools via MCP servers. It continues iterating until the task is complete
        or the maximum iteration limit is reached.

        Args:
            task: str - The finance monitoring task to execute (e.g., "Generate monthly
                  expense report", "Check for budget anomalies", "Send spending alerts")

        Returns:
            str: The final response from the agent after completing the task,
                 including any findings, reports generated, or actions taken.

        Raises:
            Exception: Logs and re-raises any critical errors that prevent task execution.
        """
        logger.info(f"Finance Monitor Agent starting task: {task[:100]}...")

        messages = [
            {
                "role": "user",
                "content": task
            }
        ]

        final_response = ""
        iteration = 0

        try:
            mcp_servers = self._get_mcp_servers()

            async with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
                tools=[],
                betas=["mcp-client-2025-04-04"],
                mcp_servers=mcp_servers,
            ) as stream:
                response = await stream.get_final_message()

            while iteration < self.max_iterations:
                iteration += 1
                logger.info(f"Agent iteration {iteration}/{self.max_iterations}")

                stop_reason = response.stop_reason
                logger.info(f"Stop reason: {stop_reason}")

                # Extract text content from response
                response_text = ""
                tool_uses = []

                for block in response.content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            response_text += block.text
                        elif block.type == "tool_use":
                            tool_uses.append(block)
                        elif block.type == "mcp_tool_use":
                            tool_uses.append(block)

                if response_text:
                    final_response = response_text

                # If end_turn or no tool uses, we're done
                if stop_reason == "end_turn" or not tool_uses:
                    logger.info("Agent completed task successfully")
                    break

                # Handle tool results for next iteration
                if stop_reason == "tool_use" and tool_uses:
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    tool_results = []
                    for tool_use in tool_uses:
                        tool_result = await self._process_tool_result(tool_use)
                        tool_results.append(tool_result)

                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Continue the conversation
                    try:
                        async with self.client.beta.messages.stream(
                            model=self.model,
                            max_tokens=self.max_tokens,
                            system=self.system_prompt,
                            messages=messages,
                            betas=["mcp-client-2025-04-04"],
                            mcp_servers=mcp_servers,
                        ) as stream:
                            response = await stream.get_final_message()
                    except anthropic.APIError as e:
                        logger.error(f"API error during tool result processing: {e}")
                        raise
                else:
                    # No more tool calls needed
                    break

            if iteration >= self.max_iterations:
                logger.warning(f"Reached maximum iterations ({self.max_iterations})")
                final_response += f"\n\n[Note: Task processing reached maximum iteration limit of {self.max_iterations}]"

        except anthropic.AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except anthropic.APIConnectionError as e:
            logger.error(f"API connection error: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during agent execution: {e}")
            raise

        logger.info("Finance Monitor Agent task completed")
        return final_response if final_response else "Task completed with no text output generated."

    async def _process_tool_result(self, tool_use: Any) -> dict[str, Any]:
        """
        Process a tool use block and format it as a tool result for the conversation.

        This method handles the formatting of tool results to be included in the
        message history for continued agent processing. For MCP tools, the results
        are already handled by the MCP client infrastructure.

        Args:
            tool_use: The tool use block from the assistant's response, containing
                     the tool name, input parameters, and tool use ID.

        Returns:
            dict: A formatted tool result dictionary ready to be included in the
                  messages array for the next API call.
        """
        try:
            tool_use_id = getattr(tool_use, "id", "unknown")
            tool_name = getattr(tool_use, "name", "unknown")
            tool_type = getattr(tool_use, "type", "tool_use")

            logger.info(f"Processing tool result for: {tool_name} (type: {tool_type})")

            # For MCP tool uses, format as mcp_tool_result
            if tool_type == "mcp_tool_use":
                return {
                    "type": "mcp_tool_result",
                    "tool_use_id": tool_use_id,
                    "content": f"Tool {tool_name} executed via MCP server"
                }

            # For standard tool uses
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": f"Tool {tool_name} executed successfully"
            }

        except Exception as e:
            logger.error(f"Error processing tool result: {e}")
            tool_use_id = getattr(tool_use, "id", "unknown")
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": f"Error processing tool result: {str(e)}",
                "is_error": True
            }

    async def monitor_budgets(self) -> str:
        """
        Execute a comprehensive budget monitoring cycle across all departments.

        This method triggers a full budget monitoring workflow that checks current
        spending against allocations, identifies anomalies, and sends alerts as needed.

        Returns:
            str: Summary of the monitoring cycle results including any alerts triggered.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%B %Y")

        task = f"""Execute a comprehensive budget monitoring cycle for {current_month} as of {current_date}.

Please perform the following steps:

1. READ FINANCIAL DATA:
   - Read the current budget allocations from the filesystem (look for budget_allocations.json or similar)
   - Read the current expense records for this month
   - Read historical expense data for trend analysis

2. VALIDATE VENDORS:
   - Query the registry server to validate any new vendors or cost centers found in recent expenses
   - Flag any unrecognized vendors for review

3. ANALYZE SPENDING:
   - Calculate spending percentages for each department against their budgets
   - Identify departments approaching the {self.budget_warning_threshold * 100:.0f}% warning threshold
   - Identify departments exceeding the {self.budget_critical_threshold * 100:.0f}% critical threshold
   - Detect anomalous spending patterns using statistical analysis

4. CROSS-REFERENCE CALENDAR:
   - Check calendar events for this month to correlate any spending spikes with planned activities
   - Note any upcoming events that may cause future spending increases

5. UPDATE RECORDS:
   - Write a timestamped monitoring report to the filesystem
   - Update the expense tracking log with current status

6. SEND ALERTS:
   - Send warning emails to department heads for departments at warning threshold
   - Send critical alerts to finance leadership for departments at critical threshold
   - Include specific spending data and recommended actions in all alerts

7. GENERATE SUMMARY:
   - Provide a comprehensive summary of the monitoring cycle results
   - Include key metrics, alerts triggered, and recommended actions

Today's date: {current_date}
Finance leadership contacts: {', '.join(self.finance_leadership_emails)}"""

        return await self.run(task)

    async def generate_monthly_report(self, month: str = None, year: int = None) -> str:
        """
        Generate a comprehensive monthly expense summary report.

        Creates a detailed financial report with department-level breakdowns,
        trend analysis, and variance explanations for the specified month.

        Args:
            month: str - Month name (e.g., "January"). Defaults to current month.
            year: int - Year (e.g., 2024). Defaults to current year.

        Returns:
            str: The generated monthly report content and confirmation of where it was saved.
        """
        if month is None:
            month = datetime.now().strftime("%B")
        if year is None:
            year = datetime.now().year

        report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        task = f"""Generate a comprehensive monthly expense summary report for {month} {year}.

Report Generation Date: {report_date}

Please create a detailed financial report that includes:

1. EXECUTIVE SUMMARY:
   - Total organizational spending vs. budget for {month} {year}
   - Overall budget utilization percentage
   - Number of departments over/under budget
   - Key financial highlights and concerns

2. DEPARTMENT-LEVEL BREAKDOWN:
   - For each department: allocated budget, actual spending, variance, utilization %
   - Month-over-month spending comparison
   - Year-to-date spending vs. annual budget projection

3. TREND ANALYSIS:
   - Spending trends over the past 3-6 months
   - Departments with consistently increasing spend
   - Seasonal patterns and their impact on current month

4. ANOMALY REPORT:
   - Any unusual spending patterns detected
   - Correlation with calendar events (query calendar for {month} {year} events)
   - Vendor validation status (check registry for any flagged vendors)

5. BUDGET FORECAST:
   - Projected year-end spending based on current trends
   - Departments at risk of budget overrun
   - Recommended budget adjustments

6. ACTION ITEMS:
   - Specific recommendations for each department with budget concerns
   - Required approvals or escalations

Please:
- Read all relevant financial data from the filesystem
- Validate vendor information via the registry server
- Cross-reference with calendar events for context
- Save the complete report to the filesystem as 'monthly_report_{month.lower()}_{year}.json' and 'monthly_report_{month.lower()}_{year}.txt'
- Email the report to finance leadership: {', '.join(self.finance_leadership_emails)}
- Return a summary of the report and confirmation of delivery"""

        return await self.run(task)

    async def investigate_anomaly(self, department: str, anomaly_description: str) -> str:
        """
        Investigate a specific spending anomaly for a department.

        Performs a deep-dive analysis of an identified spending anomaly,
        gathering evidence and context before escalating to stakeholders.

        Args:
            department: str - The department name where the anomaly was detected.
            anomaly_description: str - Description of the anomaly to investigate.

        Returns:
            str: Investigation findings including evidence, context, and recommended actions.
        """
        investigation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        task = f"""Investigate the following spending anomaly and provide a detailed analysis:

Department: {department}
Anomaly Description: {anomaly_description}
Investigation Date: {investigation_date}

Investigation Steps:

1. GATHER EVIDENCE:
   - Read all expense records for {department} from the filesystem
   - Pull historical spending data for the past 6 months for comparison
   - Identify the specific transactions contributing to the anomaly

2. VALIDATE TRANSACTIONS:
   - Query the registry server to validate all vendors involved in suspicious transactions
   - Check if cost centers are properly authorized
   - Flag any unrecognized or unauthorized vendors

3. CONTEXTUAL ANALYSIS:
   - Check the calendar for events in {department} that might explain the spending
   - Compare against similar periods in previous years
   - Assess whether the anomaly is isolated or part of a pattern

4. RISK ASSESSMENT:
   - Determine the financial impact of the anomaly
   - Assess whether this represents a policy violation, error, or legitimate expense
   - Calculate the risk level: Low / Medium / High / Critical

5. DOCUMENTATION:
   - Write a detailed investigation report to the filesystem
   - Include all evidence, timeline, and findings
   - Timestamp all entries

6. ESCALATION:
   - If risk level is High or Critical, send immediate alert to finance leadership
   - Send findings to the {department} department head
   - Include specific evidence and recommended corrective actions

Finance leadership contacts: {', '.join(self.finance_leadership_emails)}

Provide a comprehensive investigation report with clear findings and recommended next steps."""

        return await self.run(task)


async def main():
    """
    Main entry point for running the Finance Monitor Agent.

    Demonstrates the agent's capabilities by running a budget monitoring cycle,
    generating a monthly report, and investigating a sample anomaly.
    """
    agent = FinanceMonitorAgent()

    logger.info("Starting Finance Monitor Agent demonstration...")

    # Example 1: Run a budget monitoring cycle
    logger.info("\n=== Running Budget Monitoring Cycle ===")
    try:
        monitoring_result = await agent.monitor_budgets()
        logger.info(f"Monitoring Result:\n{monitoring_result}")
    except Exception as e:
        logger.error(f"Budget monitoring failed: {e}")

    # Example 2: Generate monthly report
    logger.info("\n=== Generating Monthly Report ===")
    try:
        report_result = await agent.generate_monthly_report()
        logger.info(f"Report Result:\n{report_result}")
    except Exception as e:
        logger.error(f"Monthly report generation failed: {e}")

    # Example 3: Run a custom task
    logger.info("\n=== Running Custom Finance Task ===")
    try:
        custom_task = """
        Check if the Engineering department has any pending expense reports 
        that haven't been approved yet, and send a reminder to the department head 
        if there are any items older than 30 days.
        """
        custom_result = await agent.run(custom_task)
        logger.info(f"Custom Task Result:\n{custom_result}")
    except Exception as e:
        logger.error(f"Custom task failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())