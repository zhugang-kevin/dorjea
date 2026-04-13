import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Any

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketTrendsResearchAgent:
    """
    Market Trends Research Agent for identifying and analyzing emerging market trends.

    This agent monitors competitive landscapes, consumer behavior, regulatory environments,
    and technological advancements to deliver actionable intelligence summaries for the
    strategy team.
    """

    def __init__(self):
        """
        Initialize the MarketTrendsResearchAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            REGISTRY_SERVER_URL: URL for the registry server
            REGISTRY_API_KEY: API key for registry server authentication
            WEB_SEARCH_API_KEY: API key for web search service
            WEB_SEARCH_ENGINE_ID: Search engine ID for web search
            AGENT_MODEL: Claude model to use (defaults to claude-sonnet-4-6)
            AGENT_MAX_TOKENS: Maximum tokens for responses (defaults to 8096)
            ORGANIZATION_NAME: Name of the organization for context
            STRATEGIC_DOMAINS: Comma-separated list of strategic domains to monitor
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.registry_server_url = os.getenv("REGISTRY_SERVER_URL", "http://localhost:8080")
        self.registry_api_key = os.getenv("REGISTRY_API_KEY")
        self.web_search_api_key = os.getenv("WEB_SEARCH_API_KEY")
        self.web_search_engine_id = os.getenv("WEB_SEARCH_ENGINE_ID")
        self.model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "8096"))
        self.organization_name = os.getenv("ORGANIZATION_NAME", "the organization")
        self.strategic_domains = [
            domain.strip()
            for domain in os.getenv("STRATEGIC_DOMAINS", "technology,finance,healthcare").split(",")
        ]

        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.tools = [
            {
                "name": "web_search",
                "description": (
                    "Search the web for current market trends, news, competitor activities, "
                    "regulatory changes, and industry developments. Use this to gather fresh "
                    "intelligence from diverse sources across industries."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant market information",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of search results to retrieve (default: 10)",
                            "default": 10,
                        },
                        "date_restrict": {
                            "type": "string",
                            "description": "Restrict results by date (e.g., 'd7' for last 7 days, 'm1' for last month)",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "registry_server",
                "description": (
                    "Access the organization's registry server to retrieve strategic interests, "
                    "known competitors, target markets, and organizational priorities. Use this "
                    "to cross-reference market findings against organizational context."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["get", "list", "search"],
                            "description": "Action to perform on the registry",
                        },
                        "resource_type": {
                            "type": "string",
                            "description": "Type of resource to access (e.g., 'strategic_interests', 'competitors', 'markets', 'priorities')",
                        },
                        "resource_id": {
                            "type": "string",
                            "description": "Specific resource ID for 'get' action",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query for 'search' action",
                        },
                    },
                    "required": ["action", "resource_type"],
                },
            },
        ]

        self.system_prompt = f"""You are the Market Trends Research Agent for {self.organization_name}, 
a specialized AI analyst focused on identifying and analyzing emerging market trends relevant to 
the organization's strategic interests.

Your core responsibilities:
1. Monitor and identify emerging market trends across relevant industries using web search and registry data
2. Synthesize information from multiple sources into structured, actionable market intelligence summaries
3. Track competitor movements, product launches, and strategic pivots
4. Analyze shifts in consumer behavior, demand patterns, and sentiment
5. Identify regulatory, geopolitical, or macroeconomic developments affecting strategic planning
6. Deliver trend reports with prioritized insights ranked by relevance and urgency
7. Cross-reference findings against the organization's known strategic interests in the registry server
8. Flag high-confidence signals of market disruption or opportunity

Strategic domains to monitor: {', '.join(self.strategic_domains)}

When conducting research:
- Always search for multiple perspectives and cross-validate information
- Prioritize recent data (last 30-90 days for fast-moving trends)
- Distinguish between confirmed facts and emerging signals
- Rate each finding by confidence level (High/Medium/Low) and urgency (Critical/High/Medium/Low)
- Structure your final report with executive summary, key findings, competitive intelligence, 
  and recommended actions
- Always check the registry server for organizational context before finalizing recommendations

Current date: {datetime.now().strftime('%Y-%m-%d')}"""

    async def _execute_web_search(self, query: str, num_results: int = 10, date_restrict: str = None) -> dict[str, Any]:
        """
        Execute a web search using the configured search API.

        Args:
            query: The search query string
            num_results: Number of results to retrieve
            date_restrict: Optional date restriction string

        Returns:
            Dictionary containing search results or error information
        """
        try:
            import urllib.request
            import urllib.parse

            base_url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.web_search_api_key,
                "cx": self.web_search_engine_id,
                "q": query,
                "num": min(num_results, 10),
            }

            if date_restrict:
                params["dateRestrict"] = date_restrict

            url = f"{base_url}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(url, headers={"User-Agent": "MarketTrendsAgent/1.0"})

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            results = []
            for item in data.get("items", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": item.get("displayLink", ""),
                        "date": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", ""),
                    }
                )

            return {
                "success": True,
                "query": query,
                "total_results": data.get("searchInformation", {}).get("totalResults", "0"),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Web search failed for query '{query}': {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "results": [],
                "note": "Search service unavailable. Using cached/simulated data for demonstration.",
            }

    async def _execute_registry_query(
        self,
        action: str,
        resource_type: str,
        resource_id: str = None,
        query: str = None,
    ) -> dict[str, Any]:
        """
        Execute a query against the organization's registry server.

        Args:
            action: The action to perform (get, list, search)
            resource_type: Type of resource to access
            resource_id: Optional specific resource ID
            query: Optional search query

        Returns:
            Dictionary containing registry data or error information
        """
        try:
            import urllib.request
            import urllib.parse

            headers = {
                "Authorization": f"Bearer {self.registry_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "MarketTrendsAgent/1.0",
            }

            if action == "get" and resource_id:
                url = f"{self.registry_server_url}/api/v1/{resource_type}/{resource_id}"
            elif action == "search" and query:
                params = urllib.parse.urlencode({"q": query, "type": resource_type})
                url = f"{self.registry_server_url}/api/v1/search?{params}"
            else:
                url = f"{self.registry_server_url}/api/v1/{resource_type}"

            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            return {"success": True, "action": action, "resource_type": resource_type, "data": data}

        except Exception as e:
            logger.error(f"Registry query failed for {action} {resource_type}: {str(e)}")
            return {
                "success": False,
                "action": action,
                "resource_type": resource_type,
                "error": str(e),
                "data": self._get_fallback_registry_data(resource_type),
                "note": "Registry server unavailable. Using default organizational context.",
            }

    def _get_fallback_registry_data(self, resource_type: str) -> dict[str, Any]:
        """
        Provide fallback registry data when the registry server is unavailable.

        Args:
            resource_type: The type of resource requested

        Returns:
            Dictionary with default organizational context data
        """
        fallback_data = {
            "strategic_interests": {
                "domains": self.strategic_domains,
                "focus_areas": ["market expansion", "digital transformation", "sustainability"],
                "time_horizon": "3-5 years",
            },
            "competitors": {
                "primary": ["Major industry players in " + domain for domain in self.strategic_domains],
                "emerging": ["Startups and disruptors in key markets"],
            },
            "markets": {
                "current": self.strategic_domains,
                "target": ["Adjacent markets for expansion"],
            },
            "priorities": {
                "strategic": ["Growth", "Innovation", "Operational Excellence"],
                "tactical": ["Market share", "Customer acquisition", "Cost optimization"],
            },
        }
        return fallback_data.get(resource_type, {"message": f"No fallback data for {resource_type}"})

    async def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Process a tool call and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            JSON string containing the tool execution result
        """
        try:
            if tool_name == "web_search":
                result = await self._execute_web_search(
                    query=tool_input.get("query", ""),
                    num_results=tool_input.get("num_results", 10),
                    date_restrict=tool_input.get("date_restrict"),
                )
            elif tool_name == "registry_server":
                result = await self._execute_registry_query(
                    action=tool_input.get("action", "list"),
                    resource_type=tool_input.get("resource_type", ""),
                    resource_id=tool_input.get("resource_id"),
                    query=tool_input.get("query"),
                )
            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Tool call processing failed for {tool_name}: {str(e)}")
            return json.dumps({"success": False, "error": str(e), "tool": tool_name})

    async def run(self, task: str) -> str:
        """
        Execute the market trends research agent with the given task.

        This method implements an agentic loop that:
        1. Sends the task to Claude with available tools
        2. Processes tool calls (web search, registry queries) as requested
        3. Continues until Claude produces a final response
        4. Returns the synthesized market intelligence report

        Args:
            task: The research task or question to investigate

        Returns:
            A comprehensive market intelligence report as a string

        Raises:
            Exception: If the agent encounters an unrecoverable error
        """
        logger.info(f"Starting market trends research task: {task[:100]}...")

        messages = [{"role": "user", "content": task}]

        max_iterations = 20
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"Agent iteration {iteration}/{max_iterations}")

                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=self.system_prompt,
                        tools=self.tools,
                        messages=messages,
                    )
                except anthropic.APIConnectionError as e:
                    logger.error(f"API connection error: {str(e)}")
                    return f"Error: Unable to connect to Anthropic API. {str(e)}"
                except anthropic.RateLimitError as e:
                    logger.error(f"Rate limit error: {str(e)}")
                    await asyncio.sleep(60)
                    continue
                except anthropic.APIStatusError as e:
                    logger.error(f"API status error {e.status_code}: {str(e)}")
                    return f"Error: API returned status {e.status_code}. {str(e)}"

                logger.info(f"Response stop reason: {response.stop_reason}")

                if response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text

                    logger.info("Agent completed task successfully")
                    return final_text

                if response.stop_reason == "tool_use":
                    messages.append({"role": "assistant", "content": response.content})

                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            logger.info(f"Executing tool: {block.name} with input: {json.dumps(block.input)[:200]}")

                            tool_result = await self._process_tool_call(block.name, block.input)

                            logger.info(f"Tool {block.name} completed, result length: {len(tool_result)}")

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": tool_result,
                                }
                            )

                    messages.append({"role": "user", "content": tool_results})

                else:
                    logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    return final_text if final_text else f"Agent stopped with reason: {response.stop_reason}"

            logger.warning(f"Agent reached maximum iterations ({max_iterations})")
            return (
                f"Market trends research reached maximum iterations ({max_iterations}). "
                "Partial analysis may be available in the conversation history."
            )

        except Exception as e:
            logger.error(f"Unexpected error in agent run: {str(e)}", exc_info=True)
            return f"Agent encountered an unexpected error: {str(e)}"


async def main():
    """
    Main entry point for running the Market Trends Research Agent.

    Reads the research task from the AGENT_TASK environment variable
    or uses a default comprehensive market analysis task.
    """
    agent = MarketTrendsResearchAgent()

    task = os.getenv(
        "AGENT_TASK",
        (
            "Conduct a comprehensive market trends analysis for our strategic planning. "
            "Please: 1) Search for the latest emerging trends in our key strategic domains, "
            "2) Identify major competitor movements and market disruptions in the past 30 days, "
            "3) Analyze regulatory and macroeconomic developments that could impact our strategy, "
            "4) Cross-reference findings with our organizational strategic interests from the registry, "
            "5) Deliver a prioritized intelligence report with actionable recommendations ranked by "
            "urgency and strategic relevance. Flag any critical signals requiring immediate leadership attention."
        ),
    )

    logger.info("Market Trends Research Agent starting...")
    result = await agent.run(task)

    print("\n" + "=" * 80)
    print("MARKET INTELLIGENCE REPORT")
    print("=" * 80)
    print(result)
    print("=" * 80)

    return result


if __name__ == "__main__":
    asyncio.run(main())