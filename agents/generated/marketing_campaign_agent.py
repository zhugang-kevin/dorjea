import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Any

import anthropic
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CampaignBrief(BaseModel):
    """Structured campaign brief model."""
    campaign_name: str = Field(..., description="Name of the marketing campaign")
    objective: str = Field(..., description="Primary campaign objective")
    target_audience: str = Field(..., description="Target audience description")
    channels: list[str] = Field(default_factory=list, description="Marketing channels")
    budget: float = Field(default=0.0, description="Campaign budget")
    start_date: str = Field(default="", description="Campaign start date")
    end_date: str = Field(default="", description="Campaign end date")
    kpis: list[str] = Field(default_factory=list, description="Key performance indicators")
    messaging: str = Field(default="", description="Core messaging strategy")


class ContentCalendarEntry(BaseModel):
    """Content calendar entry model."""
    date: str = Field(..., description="Publication date")
    channel: str = Field(..., description="Distribution channel")
    content_type: str = Field(..., description="Type of content")
    title: str = Field(..., description="Content title")
    owner: str = Field(default="", description="Content owner")
    status: str = Field(default="planned", description="Content status")


class PerformanceMetrics(BaseModel):
    """Campaign performance metrics model."""
    campaign_id: str = Field(..., description="Campaign identifier")
    impressions: int = Field(default=0, description="Total impressions")
    clicks: int = Field(default=0, description="Total clicks")
    conversions: int = Field(default=0, description="Total conversions")
    spend: float = Field(default=0.0, description="Total spend")
    revenue: float = Field(default=0.0, description="Total revenue")
    roi: float = Field(default=0.0, description="Return on investment")
    ctr: float = Field(default=0.0, description="Click-through rate")
    cpa: float = Field(default=0.0, description="Cost per acquisition")


class MarketingCampaignAgent:
    """
    Marketing Campaign Agent for designing and managing end-to-end marketing campaigns.

    This agent handles campaign strategy, brief creation, audience development,
    content calendar management, performance tracking, and optimization recommendations.
    It leverages Claude's tool-use capabilities to interact with web search, email,
    calendar, and filesystem services.
    """

    def __init__(self):
        """
        Initialize the MarketingCampaignAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            MARKETING_AGENT_MODEL: Claude model to use (defaults to claude-sonnet-4-6)
            MARKETING_AGENT_MAX_TOKENS: Maximum tokens per response (defaults to 8096)
            MARKETING_AGENT_TEMPERATURE: Temperature for responses (defaults to 0.7)
            MARKETING_CAMPAIGNS_DIR: Directory for storing campaign files (defaults to ./campaigns)
            MARKETING_KNOWLEDGE_BASE_DIR: Directory for knowledge base (defaults to ./knowledge_base)
            MARKETING_DEFAULT_CURRENCY: Default currency (defaults to USD)
            MARKETING_ROI_THRESHOLD: ROI threshold for alerts (defaults to 0.1)
            MARKETING_PERFORMANCE_CHECK_INTERVAL: Hours between performance checks (defaults to 24)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.model = os.getenv("MARKETING_AGENT_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("MARKETING_AGENT_MAX_TOKENS", "8096"))
        self.temperature = float(os.getenv("MARKETING_AGENT_TEMPERATURE", "0.7"))
        self.campaigns_dir = os.getenv("MARKETING_CAMPAIGNS_DIR", "./campaigns")
        self.knowledge_base_dir = os.getenv("MARKETING_KNOWLEDGE_BASE_DIR", "./knowledge_base")
        self.default_currency = os.getenv("MARKETING_DEFAULT_CURRENCY", "USD")
        self.roi_threshold = float(os.getenv("MARKETING_ROI_THRESHOLD", "0.1"))
        self.performance_check_interval = int(
            os.getenv("MARKETING_PERFORMANCE_CHECK_INTERVAL", "24")
        )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.conversation_history: list[dict[str, Any]] = []

        self.tools = self._define_tools()
        self.system_prompt = self._build_system_prompt()

        logger.info("MarketingCampaignAgent initialized with model: %s", self.model)

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for the marketing campaign agent.

        Returns:
            str: The complete system prompt defining agent behavior and capabilities.
        """
        return f"""You are an expert Marketing Campaign Agent specializing in designing and managing 
full end-to-end marketing campaigns from conception to measurement.

Your core responsibilities include:
1. Design end-to-end campaign strategies aligned to business objectives, including channel mix, 
   messaging architecture, budget allocation, and timeline planning
2. Produce comprehensive campaign briefs that provide creative, content, and media teams with all 
   information required to execute without ambiguity
3. Develop detailed buyer personas using available audience data, market research, and behavioral 
   insights to guide targeting and messaging decisions
4. Build and maintain structured content calendars that map all campaign assets to dates, channels, 
   owners, formats, and distribution plans
5. Monitor campaign performance against defined KPIs at scheduled intervals and produce timely 
   performance reports with actionable insights
6. Conduct mid-campaign optimization reviews and produce data-driven recommendations to improve 
   performance against targets
7. Deliver post-campaign measurement reports that calculate ROI and all defined KPIs with 
   documented methodology
8. Maintain a campaign knowledge base capturing reusable insights, audience learnings, and channel 
   benchmarks for future campaign planning
9. Coordinate campaign brief distribution and stakeholder alignment communications across relevant teams
10. Identify and escalate campaign risks, budget anomalies, and performance issues that exceed 
    defined thresholds

Configuration:
- Default Currency: {self.default_currency}
- ROI Alert Threshold: {self.roi_threshold * 100}%
- Performance Check Interval: {self.performance_check_interval} hours
- Campaigns Directory: {self.campaigns_dir}
- Knowledge Base Directory: {self.knowledge_base_dir}

When working on campaigns:
- Always structure your work systematically and document everything
- Use data-driven insights to inform all recommendations
- Maintain clear audit trails for all campaign decisions
- Proactively identify risks and opportunities
- Ensure all stakeholders have the information they need
- Calculate and report ROI with full methodology transparency

Use the available tools to:
- Search the web for market research, competitor analysis, and industry benchmarks
- Send emails for stakeholder communications and brief distribution
- Manage calendar events for campaign milestones and performance reviews
- Read and write files for campaign documentation, briefs, and reports

Always provide actionable, specific recommendations backed by data and reasoning.
Current date: {datetime.now().strftime('%Y-%m-%d')}"""

    def _define_tools(self) -> list[dict[str, Any]]:
        """
        Define the tools available to the marketing campaign agent.

        Returns:
            list[dict]: List of tool definitions for web search, email, calendar, and filesystem.
        """
        return [
            {
                "name": "web_search",
                "description": "Search the web for market research, competitor analysis, industry benchmarks, audience insights, and campaign best practices. Use this to gather data-driven insights for campaign planning and optimization.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant marketing information"
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["general", "news", "research", "competitor"],
                            "description": "Type of search to perform"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "email",
                "description": "Send emails for campaign brief distribution, stakeholder communications, performance reports, and team coordination. Use this to keep all stakeholders aligned and informed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipient email addresses"
                        },
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of CC email addresses"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content (supports HTML)"
                        },
                        "attachments": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths to attach"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high"],
                            "description": "Email priority level",
                            "default": "normal"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "calendar",
                "description": "Create and manage calendar events for campaign milestones, content publication dates, performance review meetings, and stakeholder check-ins.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create", "update", "delete", "list", "get"],
                            "description": "Calendar action to perform"
                        },
                        "title": {
                            "type": "string",
                            "description": "Event title"
                        },
                        "start_datetime": {
                            "type": "string",
                            "description": "Event start date and time (ISO 8601 format)"
                        },
                        "end_datetime": {
                            "type": "string",
                            "description": "Event end date and time (ISO 8601 format)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Event description and details"
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee email addresses"
                        },
                        "location": {
                            "type": "string",
                            "description": "Event location or meeting link"
                        },
                        "event_id": {
                            "type": "string",
                            "description": "Event ID for update/delete/get operations"
                        },
                        "date_range_start": {
                            "type": "string",
                            "description": "Start date for listing events (ISO 8601 format)"
                        },
                        "date_range_end": {
                            "type": "string",
                            "description": "End date for listing events (ISO 8601 format)"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "filesystem_server",
                "description": "Read and write files for campaign documentation, briefs, content calendars, performance reports, and knowledge base entries. Use this to maintain persistent campaign records.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["read", "write", "append", "list", "delete", "exists", "mkdir"],
                            "description": "Filesystem action to perform"
                        },
                        "path": {
                            "type": "string",
                            "description": "File or directory path"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write or append to file"
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)",
                            "default": "utf-8"
                        },
                        "create_dirs": {
                            "type": "boolean",
                            "description": "Create parent directories if they don't exist",
                            "default": True
                        }
                    },
                    "required": ["action", "path"]
                }
            }
        ]

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Execute a tool call and return the result.

        This method simulates tool execution by processing the tool inputs and
        returning structured responses. In production, these would connect to
        actual service integrations.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Dictionary of input parameters for the tool

        Returns:
            str: JSON-encoded result of the tool execution
        """
        try:
            if tool_name == "web_search":
                return await self._execute_web_search(tool_input)
            elif tool_name == "email":
                return await self._execute_email(tool_input)
            elif tool_name == "calendar":
                return await self._execute_calendar(tool_input)
            elif tool_name == "filesystem_server":
                return await self._execute_filesystem(tool_input)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            logger.error("Tool execution error for %s: %s", tool_name, str(e))
            return json.dumps({"error": str(e), "tool": tool_name})

    async def _execute_web_search(self, tool_input: dict[str, Any]) -> str:
        """
        Execute a web search operation.

        Args:
            tool_input: Dictionary containing query, search_type, and max_results

        Returns:
            str: JSON-encoded search results
        """
        try:
            query = tool_input.get("query", "")
            search_type = tool_input.get("search_type", "general")
            max_results = tool_input.get("max_results", 10)

            logger.info("Web search: query='%s', type='%s'", query, search_type)

            result = {
                "status": "success",
                "query": query,
                "search_type": search_type,
                "results_count": max_results,
                "results": [
                    {
                        "title": f"Marketing insights for: {query}",
                        "url": f"https://example.com/marketing/{query.replace(' ', '-')}",
                        "snippet": f"Comprehensive analysis and insights about {query} for marketing campaigns. "
                                   f"Industry benchmarks show significant opportunities in this area.",
                        "date": datetime.now().strftime("%Y-%m-%d")
                    }
                ],
                "timestamp": datetime.now().isoformat()
            }
            return json.dumps(result)
        except Exception as e:
            logger.error("Web search error: %s", str(e))
            return json.dumps({"error": str(e), "status": "failed"})

    async def _execute_email(self, tool_input: dict[str, Any]) -> str:
        """
        Execute an email send operation.

        Args:
            tool_input: Dictionary containing to, cc, subject, body, attachments, and priority

        Returns:
            str: JSON-encoded email send result
        """
        try:
            to_addresses = tool_input.get("to", [])
            subject = tool_input.get("subject", "")
            body = tool_input.get("body", "")
            cc_addresses = tool_input.get("cc", [])
            attachments = tool_input.get("attachments", [])
            priority = tool_input.get("priority", "normal")

            logger.info(
                "Email sent: to=%s, subject='%s', priority='%s'",
                to_addresses, subject, priority
            )

            result = {
                "status": "success",
                "message_id": f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "to": to_addresses,
                "cc": cc_addresses,
                "subject": subject,
                "priority": priority,
                "attachments_count": len(attachments),
                "sent_at": datetime.now().isoformat()
            }
            return json.dumps(result)
        except Exception as e:
            logger.error("Email error: %s", str(e))
            return json.dumps({"error": str(e), "status": "failed"})

    async def _execute_calendar(self, tool_input: dict[str, Any]) -> str:
        """
        Execute a calendar operation (create, update, delete, list, get).

        Args:
            tool_input: Dictionary containing action and event details

        Returns:
            str: JSON-encoded calendar operation result
        """
        try:
            action = tool_input.get("action", "")
            logger.info("Calendar action: %s", action)

            if action == "create":
                result = {
                    "status": "success",
                    "action": "create",
                    "event_id": f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "title": tool_input.get("title", ""),
                    "start_datetime": tool_input.get("start_datetime", ""),
                    "end_datetime": tool_input.get("end_datetime", ""),
                    "attendees": tool_input.get("attendees", []),
                    "created_at": datetime.now().isoformat()
                }
            elif action == "list":
                result = {
                    "status": "success",
                    "action": "list",
                    "events": [],
                    "date_range_start": tool_input.get("date_range_start", ""),
                    "date_range_end": tool_input.get("date_range_end", ""),
                    "retrieved_at": datetime.now().isoformat()
                }
            elif action in ["update", "delete", "get"]:
                result = {
                    "status": "success",
                    "action": action,
                    "event_id": tool_input.get("event_id", ""),
                    "processed_at": datetime.now().isoformat()
                }
            else:
                result = {"status": "error", "message": f"Unknown calendar action: {action}"}

            return json.dumps(result)
        except Exception as e:
            logger.error("Calendar error: %s", str(e))
            return json.dumps({"error": str(e), "status": "failed"})

    async def _execute_filesystem(self, tool_input: dict[str, Any]) -> str:
        """
        Execute a filesystem operation (read, write, append, list, delete, exists, mkdir).

        Args:
            tool_input: Dictionary containing action, path, content, and options

        Returns:
            str: JSON-encoded filesystem operation result
        """
        try:
            action = tool_input.get("action", "")
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            encoding = tool_input.get("encoding", "utf-8")
            create_dirs = tool_input.get("create_dirs", True)

            logger.info("Filesystem action: %s on path: %s", action, path)

            if action == "write":
                if create_dirs:
                    dir_path = os.path.dirname(path)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                with open(path, "w", encoding=encoding) as f:
                    f.write(content)
                result = {
                    "status": "success",
                    "action": "write",
                    "path": path,
                    "bytes_written": len(content.encode(encoding)),
                    "timestamp": datetime.now().isoformat()
                }

            elif action == "read":
                if os.path.exists(path):
                    with open(path, "r", encoding=encoding) as f:
                        file_content = f.read()
                    result = {
                        "status": "success",
                        "action": "read",
                        "path": path,
                        "content": file_content,
                        "size": len(file_content),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    result = {
                        "status": "error",
                        "action": "read",
                        "path": path,
                        "message": "File not found"
                    }

            elif action == "append":
                if create_dirs:
                    dir_path = os.path.dirname(path)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                with open(path, "a", encoding=encoding) as f:
                    f.write(content)
                result = {
                    "status": "success",
                    "action": "append",
                    "path": path,
                    "bytes_appended": len(content.encode(encoding)),
                    "timestamp": datetime.now().isoformat()
                }

            elif action == "list":
                if os.path.exists(path):
                    entries = os.listdir(path)
                    result = {
                        "status": "success",
                        "action": "list",
                        "path": path,
                        "entries": entries,
                        "count": len(entries),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    result = {
                        "status": "error",
                        "action": "list",
                        "path": path,
                        "message": "Directory not found"
                    }

            elif action == "delete":
                if os.path.exists(path):
                    os.remove(path)
                    result = {
                        "status": "success",
                        "action": "delete",
                        "path": path,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    result = {
                        "status": "error",
                        "action": "delete",
                        "path": path,
                        "message": "File not found"
                    }

            elif action == "exists":
                result = {
                    "status": "success",
                    "action": "exists",
                    "path": path,
                    "exists": os.path.exists(path),
                    "is_file": os.path.isfile(path),
                    "is_dir": os.path.isdir(path),
                    "timestamp": datetime.now().isoformat()
                }

            elif action == "mkdir":
                os.makedirs(path, exist_ok=True)
                result = {
                    "status": "success",
                    "action": "mkdir",
                    "path": path,
                    "timestamp": datetime.now().isoformat()
                }

            else:
                result = {"status": "error", "message": f"Unknown filesystem action: {action}"}

            return json.dumps(result)
        except Exception as e:
            logger.error("Filesystem error: %s", str(e))
            return json.dumps({"error": str(e), "status": "failed"})

    async def _process_tool_calls(self, response: anthropic.types.Message) -> list[dict[str, Any]]:
        """
        Process all tool calls from a Claude response.

        Args:
            response: The Anthropic message response containing tool use blocks

        Returns:
            list[dict]: List of tool results to send back to Claude
        """
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_name = content_block.name
                tool_input = content_block.input
                tool_use_id = content_block.id

                logger.info("Executing tool: %s", tool_name)

                try:
                    result = await self._execute_tool(tool_name, tool_input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result
                    })
                except Exception as e:
                    logger.error("Tool call processing error: %s", str(e))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True
                    })

        return tool_results

    async def run(self, task: str) -> str:
        """
        Execute a marketing campaign task using the agent.

        This method processes the given task through an agentic loop, allowing
        Claude to use tools iteratively until the task is complete. It handles
        campaign strategy, brief creation, content calendars, performance tracking,
        and all other marketing campaign responsibilities.

        Args:
            task: The marketing task to execute, such as creating a campaign brief,
                  building a content calendar, analyzing performance metrics, or
                  generating optimization recommendations.

        Returns:
            str: The final response from the agent containing the completed work,
                 recommendations, or requested deliverables.

        Raises:
            Exception: If there's a critical error in the agent execution that
                      cannot be recovered from.
        """
        logger.info("Starting marketing campaign task: %s", task[:100])

        self.conversation_history.append({
            "role": "user",
            "content": task
        })

        max_iterations = 20
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                logger.info("Agent iteration %d/%d", iteration, max_iterations)

                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=self.system_prompt,
                        tools=self.tools,
                        messages=self.conversation_history
                    )
                except anthropic.APIConnectionError as e:
                    logger.error("API connection error: %s", str(e))
                    return f"Connection error while processing campaign task: {str(e)}"
                except anthropic.RateLimitError as e:
                    logger.error("Rate limit error: %s", str(e))
                    await asyncio.sleep(60)
                    continue
                except anthropic.APIStatusError as e:
                    logger.error("API status error %d: %s", e.status_code, str(e))
                    return f"API error while processing campaign task: {str(e)}"

                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

                if response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text

                    logger.info("Task completed after %d iterations", iteration)
                    return final_text

                elif response.stop_reason == "tool_use":
                    try:
                        tool_results = await self._process_tool_calls(response)

                        self.conversation_history.append({
                            "role": "user",
                            "content": tool_results
                        })
                    except Exception as e:
                        logger.error("Tool processing error: %s", str(e))
                        self.conversation_history.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": "error",
                                "content": json.dumps({"error": str(e)}),
                                "is_error": True
                            }]
                        })

                elif response.stop_reason == "max_tokens":
                    logger.warning("Max tokens reached, requesting continuation")
                    self.conversation_history.append({
                        "role": "user",
                        "content": "Please continue from where you left off."
                    })

                else:
                    logger.warning("Unexpected stop reason: %s", response.stop_reason)
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    return final_text if final_text else f"Task ended with reason: {response.stop_reason}"

            logger.warning("Max iterations reached for task")
            return "Maximum iterations reached. The campaign task may require breaking into smaller subtasks."

        except Exception as e:
            logger.error("Critical error in agent run: %s", str(e))
            return f"Critical error processing marketing campaign task: {str(e)}"

    def reset_conversation(self):
        """
        Reset the conversation history for a new campaign task.

        This should be called between unrelated campaign tasks to prevent
        context from one campaign affecting another.
        """
        self.conversation_history = []
        logger.info("Conversation history reset")

    def get_conversation_summary(self) -> dict[str, Any]:
        """
        Get a summary of the current conversation state.

        Returns:
            dict: Summary containing message count, tool calls made, and
                  conversation length statistics.
        """
        tool_calls = sum(
            1 for msg in self.conversation_history
            if isinstance(msg.get("content"), list)
            and any(
                isinstance(block, dict) and block.get("type") == "tool_use"
                for block in msg["content"]
            )
        )

        return {
            "total_messages": len(self.conversation_history),
            "tool_calls_made": tool_calls,
            "model": self.model,
            "campaigns_dir": self.campaigns_dir,
            "knowledge_base_dir": self.knowledge_base_dir
        }


async def main():
    """
    Main entry point for testing the MarketingCampaignAgent.

    Demonstrates the agent's capabilities with a sample campaign planning task.
    """
    try:
        agent = MarketingCampaignAgent()

        task = """Create a comprehensive Q4 holiday marketing campaign for an e-commerce 
        fashion brand targeting millennials aged 25-35. Include:
        1. Campaign strategy with channel mix and budget allocation
        2. Detailed campaign brief for the creative team
        3. Buyer persona for the primary target audience
        4. Content calendar for November-December
        5. KPIs and measurement framework
        6. Risk assessment and mitigation strategies
        
        The campaign budget is $150,000 USD and the primary goal is to increase 
        holiday season revenue by 35% compared to last year."""

        result = await agent.run(task)
        print("Campaign Planning Result:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        summary = agent.get_conversation_summary()
        print(f"\nConversation Summary: {json.dumps(summary, indent=2)}")

    except ValueError as e:
        logger.error("Configuration error: %s", str(e))
        print(f"Configuration error: {str(e)}")
        print("Please ensure ANTHROPIC_API_KEY environment variable is set.")
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        print(f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())