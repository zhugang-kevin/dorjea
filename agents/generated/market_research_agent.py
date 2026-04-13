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


class ResearchTask(BaseModel):
    """Represents a structured research task with metadata."""

    task_id: str = Field(description="Unique identifier for the research task")
    query: str = Field(description="The research query or objective")
    department: str = Field(description="Requesting department")
    created_at: str = Field(description="ISO timestamp of task creation")
    status: str = Field(default="pending", description="Current task status")


class ResearchFinding(BaseModel):
    """Represents a structured research finding."""

    source: str = Field(description="Source of the finding")
    content: str = Field(description="The actual finding content")
    relevance_score: float = Field(description="Relevance score from 0.0 to 1.0")
    timestamp: str = Field(description="When the finding was captured")
    tags: list[str] = Field(default_factory=list, description="Categorical tags")


class MarketResearchAgent:
    """
    Market Research Agent for competitive intelligence and market analysis.

    This agent serves as the primary market intelligence and competitive analysis
    researcher for the strategy team. It continuously monitors industry sources,
    competitor activity, and emerging market trends, synthesizing raw data into
    structured, actionable deliverables.

    The agent uses Claude claude-sonnet-4-6 with tool use to orchestrate web searches,
    filesystem operations, and registry queries to produce comprehensive research
    outputs including competitive landscapes, trend briefings, and executive summaries.
    """

    SYSTEM_PROMPT = """You are an expert market research analyst and competitive intelligence specialist for the strategy team.

Your mission is to conduct thorough, accurate market research and competitive analysis. You operate with a research-first mindset, prioritizing:
- Accuracy and factual correctness
- Source credibility and cross-referencing
- Relevance to organizational strategic objectives
- Actionable insights with clear strategic implications

Your responsibilities include:
1. Conducting targeted web searches to monitor competitor activity, product launches, pricing changes, and strategic moves
2. Aggregating and analyzing industry reports, market sizing data, and sector trends
3. Building and maintaining competitive landscape documents via the filesystem server
4. Querying the registry server to track company registrations, patent filings, and regulatory changes
5. Synthesizing multi-source research into concise executive summaries
6. Identifying emerging market opportunities or threats with supporting evidence
7. Maintaining a structured research archive organized by topic, date, and strategic relevance
8. Validating source credibility and cross-referencing findings across multiple sources

When conducting research:
- Always search multiple sources before drawing conclusions
- Cross-reference findings to validate accuracy
- Organize findings with clear structure and strategic context
- Flag high-priority insights that require immediate strategic attention
- Store research artifacts systematically using the filesystem server
- Include confidence levels and source quality assessments in your outputs

Format your final deliverables as structured reports with:
- Executive Summary (key findings and strategic implications)
- Detailed Findings (organized by topic)
- Competitive Intelligence (specific competitor insights)
- Market Trends (emerging patterns and opportunities)
- Recommended Actions (prioritized next steps)
- Sources and Confidence Assessment"""

    def __init__(self) -> None:
        """
        Initialize the MarketResearchAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            MARKET_RESEARCH_MODEL: Claude model to use (defaults to claude-sonnet-4-6)
            MARKET_RESEARCH_MAX_TOKENS: Maximum tokens for responses (defaults to 8192)
            MARKET_RESEARCH_TEMPERATURE: Temperature for generation (defaults to 0.3)
            FILESYSTEM_SERVER_URL: URL for the filesystem MCP server
            FILESYSTEM_SERVER_API_KEY: API key for filesystem server
            REGISTRY_SERVER_URL: URL for the registry MCP server
            REGISTRY_SERVER_API_KEY: API key for registry server
            WEB_SEARCH_API_KEY: API key for web search service
            WEB_SEARCH_ENGINE_ID: Search engine identifier
            RESEARCH_ARCHIVE_BASE_PATH: Base path for research archive storage
            DEPARTMENT: Department identifier (defaults to 'research')
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.model = os.getenv("MARKET_RESEARCH_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("MARKET_RESEARCH_MAX_TOKENS", "8192"))
        self.temperature = float(os.getenv("MARKET_RESEARCH_TEMPERATURE", "0.3"))

        self.filesystem_server_url = os.getenv("FILESYSTEM_SERVER_URL", "")
        self.filesystem_server_api_key = os.getenv("FILESYSTEM_SERVER_API_KEY", "")

        self.registry_server_url = os.getenv("REGISTRY_SERVER_URL", "")
        self.registry_server_api_key = os.getenv("REGISTRY_SERVER_API_KEY", "")

        self.web_search_api_key = os.getenv("WEB_SEARCH_API_KEY", "")
        self.web_search_engine_id = os.getenv("WEB_SEARCH_ENGINE_ID", "")

        self.research_archive_base_path = os.getenv(
            "RESEARCH_ARCHIVE_BASE_PATH", "/research/archive"
        )
        self.department = os.getenv("DEPARTMENT", "research")

        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.tools = self._define_tools()

        logger.info(
            "MarketResearchAgent initialized for department: %s", self.department
        )

    def _define_tools(self) -> list[dict[str, Any]]:
        """
        Define the tool schemas available to the agent.

        Returns:
            list[dict]: List of tool definitions in Anthropic tool format,
                       covering web search, filesystem operations, and registry queries.
        """
        return [
            {
                "name": "web_search",
                "description": (
                    "Search the web for current information about competitors, market trends, "
                    "industry news, product launches, pricing data, and strategic developments. "
                    "Use specific, targeted queries to find high-quality, relevant sources. "
                    "Returns a list of search results with titles, URLs, and snippets."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query. Be specific and targeted for best results.",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (1-20, default 10)",
                            "default": 10,
                        },
                        "date_restrict": {
                            "type": "string",
                            "description": "Restrict results by date: 'd1' (past day), 'w1' (past week), 'm1' (past month), 'y1' (past year)",
                        },
                        "site_restrict": {
                            "type": "string",
                            "description": "Restrict search to specific domain (e.g., 'techcrunch.com')",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "filesystem_read",
                "description": (
                    "Read files from the research archive filesystem. Use this to retrieve "
                    "previously stored research documents, competitive landscapes, trend briefings, "
                    "and historical findings. Supports reading individual files or listing directory contents."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File or directory path to read. Use absolute paths starting with the archive base path.",
                        },
                        "operation": {
                            "type": "string",
                            "enum": ["read_file", "list_directory", "file_exists"],
                            "description": "Operation to perform: read_file (get file contents), list_directory (list files), file_exists (check existence)",
                            "default": "read_file",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "filesystem_write",
                "description": (
                    "Write or update files in the research archive filesystem. Use this to store "
                    "research findings, competitive landscapes, trend briefings, and executive summaries. "
                    "Organize files by topic, date, and strategic relevance following the archive structure."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path where content should be written. Use descriptive names with dates.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file. Use markdown format for research documents.",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["write", "append", "create_directory"],
                            "description": "Write mode: write (overwrite), append (add to existing), create_directory (create folder)",
                            "default": "write",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional metadata to store with the file (tags, category, relevance)",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "registry_query",
                "description": (
                    "Query the business and patent registry to track company registrations, "
                    "patent filings, trademark applications, regulatory filings, and corporate "
                    "structure changes. Essential for monitoring competitor legal and IP activity."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": [
                                "company_registration",
                                "patent_filing",
                                "trademark",
                                "regulatory_filing",
                                "corporate_structure",
                                "executive_changes",
                            ],
                            "description": "Type of registry query to perform",
                        },
                        "entity_name": {
                            "type": "string",
                            "description": "Company or entity name to search for",
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Start date for query range (YYYY-MM-DD format)",
                        },
                        "date_to": {
                            "type": "string",
                            "description": "End date for query range (YYYY-MM-DD format)",
                        },
                        "jurisdiction": {
                            "type": "string",
                            "description": "Geographic jurisdiction for the query (e.g., 'US', 'EU', 'UK')",
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords to filter results",
                        },
                    },
                    "required": ["query_type", "entity_name"],
                },
            },
        ]

    def _execute_web_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a web search using the configured search API.

        Args:
            params: Search parameters including query, num_results, date_restrict, site_restrict

        Returns:
            dict: Search results with items containing title, url, snippet, and metadata.
                 Returns error information if the search fails.
        """
        try:
            import urllib.request
            import urllib.parse

            query = params.get("query", "")
            num_results = params.get("num_results", 10)
            date_restrict = params.get("date_restrict", "")
            site_restrict = params.get("site_restrict", "")

            if not self.web_search_api_key or not self.web_search_engine_id:
                return {
                    "error": "Web search not configured",
                    "message": "WEB_SEARCH_API_KEY and WEB_SEARCH_ENGINE_ID must be set",
                    "query": query,
                    "simulated": True,
                    "results": [
                        {
                            "title": f"Search result for: {query}",
                            "url": "https://example.com/result",
                            "snippet": f"This is a simulated search result for the query: {query}. Configure WEB_SEARCH_API_KEY and WEB_SEARCH_ENGINE_ID for real results.",
                            "source": "simulated",
                        }
                    ],
                }

            search_query = query
            if site_restrict:
                search_query = f"site:{site_restrict} {search_query}"

            url_params = {
                "key": self.web_search_api_key,
                "cx": self.web_search_engine_id,
                "q": search_query,
                "num": min(num_results, 10),
            }

            if date_restrict:
                url_params["dateRestrict"] = date_restrict

            base_url = "https://www.googleapis.com/customsearch/v1"
            encoded_params = urllib.parse.urlencode(url_params)
            full_url = f"{base_url}?{encoded_params}"

            with urllib.request.urlopen(full_url, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            results = []
            for item in data.get("items", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": item.get("displayLink", ""),
                        "date": item.get("pagemap", {})
                        .get("metatags", [{}])[0]
                        .get("article:published_time", ""),
                    }
                )

            return {
                "query": query,
                "total_results": data.get("searchInformation", {}).get(
                    "totalResults", 0
                ),
                "results": results,
                "search_time": data.get("searchInformation", {}).get(
                    "searchTime", 0
                ),
            }

        except Exception as e:
            logger.error("Web search failed: %s", str(e))
            return {
                "error": str(e),
                "query": params.get("query", ""),
                "results": [],
            }

    def _execute_filesystem_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a filesystem read operation against the filesystem server.

        Args:
            params: Read parameters including path and operation type

        Returns:
            dict: File contents, directory listing, or existence check result.
                 Returns error information if the operation fails.
        """
        try:
            import urllib.request
            import urllib.parse

            path = params.get("path", "")
            operation = params.get("operation", "read_file")

            if not self.filesystem_server_url:
                return {
                    "error": "Filesystem server not configured",
                    "message": "FILESYSTEM_SERVER_URL must be set",
                    "path": path,
                    "simulated": True,
                    "content": f"Simulated content for path: {path}",
                }

            headers = {"Content-Type": "application/json"}
            if self.filesystem_server_api_key:
                headers["Authorization"] = f"Bearer {self.filesystem_server_api_key}"

            request_data = json.dumps(
                {"path": path, "operation": operation}
            ).encode("utf-8")

            url = f"{self.filesystem_server_url}/api/filesystem"
            req = urllib.request.Request(
                url, data=request_data, headers=headers, method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            return data

        except Exception as e:
            logger.error("Filesystem read failed: %s", str(e))
            return {
                "error": str(e),
                "path": params.get("path", ""),
                "content": None,
            }

    def _execute_filesystem_write(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a filesystem write operation against the filesystem server.

        Args:
            params: Write parameters including path, content, mode, and optional metadata

        Returns:
            dict: Write operation result with success status and file metadata.
                 Returns error information if the operation fails.
        """
        try:
            import urllib.request

            path = params.get("path", "")
            content = params.get("content", "")
            mode = params.get("mode", "write")
            metadata = params.get("metadata", {})

            if not self.filesystem_server_url:
                logger.info(
                    "Filesystem server not configured, simulating write to: %s", path
                )
                return {
                    "success": True,
                    "simulated": True,
                    "path": path,
                    "message": f"Simulated write to {path} ({len(content)} bytes)",
                    "bytes_written": len(content),
                }

            headers = {"Content-Type": "application/json"}
            if self.filesystem_server_api_key:
                headers["Authorization"] = f"Bearer {self.filesystem_server_api_key}"

            request_data = json.dumps(
                {
                    "path": path,
                    "content": content,
                    "mode": mode,
                    "metadata": metadata,
                }
            ).encode("utf-8")

            url = f"{self.filesystem_server_url}/api/filesystem/write"
            req = urllib.request.Request(
                url, data=request_data, headers=headers, method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            return data

        except Exception as e:
            logger.error("Filesystem write failed: %s", str(e))
            return {
                "error": str(e),
                "path": params.get("path", ""),
                "success": False,
            }

    def _execute_registry_query(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a registry query against the registry server.

        Args:
            params: Query parameters including query_type, entity_name, date range,
                   jurisdiction, and keywords

        Returns:
            dict: Registry query results with filings, registrations, or corporate data.
                 Returns error information if the query fails.
        """
        try:
            import urllib.request
            import urllib.parse

            query_type = params.get("query_type", "")
            entity_name = params.get("entity_name", "")
            date_from = params.get("date_from", "")
            date_to = params.get("date_to", "")
            jurisdiction = params.get("jurisdiction", "US")
            keywords = params.get("keywords", [])

            if not self.registry_server_url:
                return {
                    "error": "Registry server not configured",
                    "message": "REGISTRY_SERVER_URL must be set",
                    "query_type": query_type,
                    "entity_name": entity_name,
                    "simulated": True,
                    "results": [
                        {
                            "type": query_type,
                            "entity": entity_name,
                            "filing_date": datetime.now().strftime("%Y-%m-%d"),
                            "status": "active",
                            "jurisdiction": jurisdiction,
                            "description": f"Simulated {query_type} record for {entity_name}",
                        }
                    ],
                }

            headers = {"Content-Type": "application/json"}
            if self.registry_server_api_key:
                headers["Authorization"] = f"Bearer {self.registry_server_api_key}"

            request_data = json.dumps(
                {
                    "query_type": query_type,
                    "entity_name": entity_name,
                    "date_from": date_from,
                    "date_to": date_to,
                    "jurisdiction": jurisdiction,
                    "keywords": keywords,
                }
            ).encode("utf-8")

            url = f"{self.registry_server_url}/api/registry/query"
            req = urllib.request.Request(
                url, data=request_data, headers=headers, method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            return data

        except Exception as e:
            logger.error("Registry query failed: %s", str(e))
            return {
                "error": str(e),
                "query_type": params.get("query_type", ""),
                "entity_name": params.get("entity_name", ""),
                "results": [],
            }

    def _process_tool_call(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Route and execute a tool call based on the tool name.

        Args:
            tool_name: Name of the tool to execute (web_search, filesystem_read,
                      filesystem_write, registry_query)
            tool_input: Input parameters for the tool

        Returns:
            dict: Tool execution result. Always returns a dict, with error information
                 if the tool name is unknown or execution fails.
        """
        try:
            logger.info("Executing tool: %s", tool_name)

            if tool_name == "web_search":
                return self._execute_web_search(tool_input)
            elif tool_name == "filesystem_read":
                return self._execute_filesystem_read(tool_input)
            elif tool_name == "filesystem_write":
                return self._execute_filesystem_write(tool_input)
            elif tool_name == "registry_query":
                return self._execute_registry_query(tool_input)
            else:
                return {
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": [
                        "web_search",
                        "filesystem_read",
                        "filesystem_write",
                        "registry_query",
                    ],
                }

        except Exception as e:
            logger.error("Tool execution failed for %s: %s", tool_name, str(e))
            return {"error": str(e), "tool": tool_name}

    async def run(self, task: str) -> str:
        """
        Execute a market research task using the agent's full capabilities.

        This method orchestrates the complete research workflow: it sends the task
        to Claude claude-sonnet-4-6 with available tools, processes tool calls in an agentic
        loop until the model signals completion, and returns the final synthesized
        research output.

        The agent will autonomously:
        - Conduct multiple web searches to gather current market data
        - Query registries for corporate and IP intelligence
        - Store findings in the research archive via the filesystem server
        - Synthesize all findings into a structured research deliverable

        Args:
            task: Natural language description of the research task. Can include
                 specific companies to analyze, market segments to cover, time
                 horizons, and desired output format.

        Returns:
            str: Complete research output as a structured markdown document
                including executive summary, detailed findings, competitive
                intelligence, market trends, and recommended actions.

        Raises:
            anthropic.APIError: If the Anthropic API call fails after retries
            ValueError: If the task string is empty or invalid
        """
        if not task or not task.strip():
            raise ValueError("Task cannot be empty")

        logger.info("Starting market research task: %s", task[:100])

        task_metadata = ResearchTask(
            task_id=f"mra_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            query=task,
            department=self.department,
            created_at=datetime.now().isoformat(),
            status="in_progress",
        )

        messages = [
            {
                "role": "user",
                "content": (
                    f"Research Task ID: {task_metadata.task_id}\n"
                    f"Department: {task_metadata.department}\n"
                    f"Initiated: {task_metadata.created_at}\n\n"
                    f"Research Objective:\n{task}\n\n"
                    f"Please conduct comprehensive research on this topic. "
                    f"Use web searches to gather current information, query the registry "
                    f"for relevant corporate/IP data, and store your findings in the "
                    f"research archive at {self.research_archive_base_path}. "
                    f"Synthesize everything into a structured research deliverable."
                ),
            }
        ]

        try:
            while True:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=messages,
                )

                logger.info(
                    "Response received - stop_reason: %s, content blocks: %d",
                    response.stop_reason,
                    len(response.content),
                )

                if response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text

                    logger.info(
                        "Research task completed: %s", task_metadata.task_id
                    )
                    return final_text

                if response.stop_reason == "tool_use":
                    messages.append(
                        {"role": "assistant", "content": response.content}
                    )

                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_result = self._process_tool_call(
                                block.name, block.input
                            )

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(tool_result, indent=2),
                                }
                            )

                    if tool_results:
                        messages.append(
                            {"role": "user", "content": tool_results}
                        )
                    else:
                        logger.warning(
                            "Tool use stop reason but no tool calls found"
                        )
                        break

                elif response.stop_reason in ("max_tokens", "stop_sequence"):
                    partial_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            partial_text += block.text

                    logger.warning(
                        "Response stopped due to: %s", response.stop_reason
                    )
                    return partial_text if partial_text else (
                        f"Research task {task_metadata.task_id} stopped: {response.stop_reason}"
                    )

                else:
                    logger.error(
                        "Unexpected stop reason: %s", response.stop_reason
                    )
                    break

        except anthropic.APIConnectionError as e:
            logger.error("API connection error: %s", str(e))
            raise
        except anthropic.RateLimitError as e:
            logger.error("Rate limit exceeded: %s", str(e))
            raise
        except anthropic.APIStatusError as e:
            logger.error("API status error %d: %s", e.status_code, str(e))
            raise

        return f"Research task {task_metadata.task_id} completed with unexpected termination."


async def main() -> None:
    """
    Entry point for running the MarketResearchAgent directly.

    Reads the research task from the RESEARCH_TASK environment variable,
    executes the agent, and prints the results to stdout. Useful for
    testing and direct invocation from the command line or scheduled jobs.
    """
    task = os.getenv(
        "RESEARCH_TASK",
        (
            "Conduct a comprehensive competitive analysis of the top 5 players "
            "in the enterprise SaaS market. Focus on recent product launches, "
            "pricing changes, and strategic moves in Q4 2024. Identify emerging "
            "opportunities and threats, and provide strategic recommendations."
        ),
    )

    agent = MarketResearchAgent()

    print(f"Starting Market Research Agent")
    print(f"Task: {task[:200]}...")
    print("-" * 80)

    result = await agent.run(task)

    print("\nResearch Output:")
    print("=" * 80)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())