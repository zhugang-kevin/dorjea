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


class OpportunityAssessment(BaseModel):
    """Structured model for opportunity assessment results."""

    opportunity_name: str = Field(description="Name or title of the business opportunity")
    market_size_estimate: str = Field(description="TAM/SAM/SOM estimates with methodology")
    competitive_landscape: str = Field(description="Key competitors and differentiation analysis")
    strategic_fit_score: float = Field(description="Score from 0-10 on strategic fit", ge=0, le=10)
    risk_summary: str = Field(description="Prioritized risks with mitigation framing")
    recommendation: str = Field(description="BUY/PASS/INVESTIGATE with rationale")
    confidence_level: str = Field(description="HIGH/MEDIUM/LOW confidence in assessment")
    missing_information: list[str] = Field(default_factory=list, description="Critical gaps requiring follow-up")
    assessment_date: str = Field(default_factory=lambda: datetime.now().isoformat())


class StrategyOpportunityAgent:
    """
    Strategy Opportunity Agent for evaluating new business opportunities.

    This agent analyzes market potential, competitive landscape, and strategic fit
    for prospective ventures. It synthesizes data-driven insights to assess viability
    and risk, delivering structured investment recommendations to support high-quality
    strategic decision-making.

    The agent maintains an institutional knowledge registry of completed assessments
    to enable pattern recognition across opportunities over time.
    """

    def __init__(self):
        """
        Initialize the StrategyOpportunityAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            FILESYSTEM_SERVER_PATH: Base path for filesystem operations
            REGISTRY_SERVER_URL: URL for the registry server
            REGISTRY_FILE_PATH: Local path for registry storage (fallback)
            AGENT_MODEL: Claude model to use (defaults to claude-sonnet-4-6)
            MAX_TOKENS: Maximum tokens for responses (defaults to 8192)
            SEARCH_MAX_RESULTS: Maximum web search results (defaults to 10)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "8192"))
        self.search_max_results = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
        self.filesystem_path = os.getenv("FILESYSTEM_SERVER_PATH", "./strategy_data")
        self.registry_server_url = os.getenv("REGISTRY_SERVER_URL", "")
        self.registry_file_path = os.getenv("REGISTRY_FILE_PATH", "./opportunity_registry.json")

        self.system_prompt = """You are a senior strategy analyst and investment advisor with deep expertise in:
- Market sizing and validation (TAM/SAM/SOM frameworks)
- Competitive intelligence and landscape mapping
- Strategic fit assessment and portfolio analysis
- Risk identification and mitigation frameworks
- Investment memo writing and decision support

Your mission is to evaluate new business opportunities with rigor, objectivity, and clarity.
You use structured, repeatable methodologies to assess viability and risk.
You communicate clearly when information is missing and formulate targeted requests to unblock assessments.

When evaluating opportunities, you:
1. Conduct independent market sizing research to validate or challenge claims
2. Map competitive landscapes to identify differentiation potential and positioning white space
3. Score strategic fit using a transparent rubric (0-10 scale)
4. Identify and prioritize risks across market, execution, regulatory, and financial dimensions
5. Produce structured investment memos optimized for founder decision-making
6. Maintain institutional knowledge by registering completed assessments

Always be data-driven, cite your sources, and clearly distinguish between facts and inferences.
When critical information is missing, explicitly list what is needed and why it matters."""

        self.tools = [
            {
                "name": "web_search",
                "description": "Search the web for market data, competitive intelligence, industry reports, and news about business opportunities. Use this to validate market size claims, identify competitors, and gather supporting evidence.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to execute"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "filesystem_server",
                "description": "Read and write files for storing assessment reports, templates, and supporting documents. Use this to save completed assessments and retrieve historical data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list", "delete"],
                            "description": "The filesystem operation to perform"
                        },
                        "path": {
                            "type": "string",
                            "description": "File or directory path relative to the base filesystem path"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write (required for write operations)"
                        }
                    },
                    "required": ["operation", "path"]
                }
            },
            {
                "name": "registry_server",
                "description": "Access the institutional knowledge registry to store and retrieve completed opportunity assessments. Use this to maintain pattern recognition across opportunities and access historical assessments.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["register", "retrieve", "list", "search", "update"],
                            "description": "The registry operation to perform"
                        },
                        "key": {
                            "type": "string",
                            "description": "Unique identifier for the registry entry"
                        },
                        "data": {
                            "type": "object",
                            "description": "Data to store in the registry (required for register/update operations)"
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query for finding relevant past assessments"
                        }
                    },
                    "required": ["operation"]
                }
            }
        ]

        os.makedirs(self.filesystem_path, exist_ok=True)
        logger.info(f"StrategyOpportunityAgent initialized with model: {self.model}")

    def _execute_web_search(self, query: str, max_results: int = 10) -> dict[str, Any]:
        """
        Execute a web search query and return structured results.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        try:
            logger.info(f"Executing web search: {query}")
            results = {
                "query": query,
                "results": [
                    {
                        "title": f"Search result for: {query}",
                        "url": f"https://example.com/search?q={query.replace(' ', '+')}",
                        "snippet": f"Relevant information about {query} from web search. This would contain actual market data, competitive intelligence, and industry insights in a production environment.",
                        "source": "web_search",
                        "timestamp": datetime.now().isoformat()
                    }
                ],
                "total_results": 1,
                "search_timestamp": datetime.now().isoformat()
            }
            return results
        except Exception as e:
            logger.error(f"Web search failed for query '{query}': {e}")
            return {"error": str(e), "query": query, "results": []}

    def _execute_filesystem_operation(self, operation: str, path: str, content: str = None) -> dict[str, Any]:
        """
        Execute a filesystem operation for reading, writing, or listing files.

        Args:
            operation: One of 'read', 'write', 'list', 'delete'
            path: File or directory path relative to the base filesystem path
            content: Content to write (required for write operations)

        Returns:
            Dictionary containing operation result and any file content
        """
        try:
            full_path = os.path.join(self.filesystem_path, path)
            logger.info(f"Filesystem operation: {operation} on {full_path}")

            if operation == "read":
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    return {"success": True, "content": file_content, "path": full_path}
                else:
                    return {"success": False, "error": f"File not found: {full_path}", "path": full_path}

            elif operation == "write":
                if content is None:
                    return {"success": False, "error": "Content required for write operation"}
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {"success": True, "message": f"File written successfully: {full_path}", "path": full_path}

            elif operation == "list":
                if os.path.exists(full_path):
                    if os.path.isdir(full_path):
                        items = os.listdir(full_path)
                        return {"success": True, "items": items, "path": full_path, "count": len(items)}
                    else:
                        return {"success": True, "items": [os.path.basename(full_path)], "path": full_path, "count": 1}
                else:
                    return {"success": False, "error": f"Path not found: {full_path}", "items": []}

            elif operation == "delete":
                if os.path.exists(full_path):
                    os.remove(full_path)
                    return {"success": True, "message": f"File deleted: {full_path}"}
                else:
                    return {"success": False, "error": f"File not found: {full_path}"}

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error(f"Filesystem operation failed: {e}")
            return {"success": False, "error": str(e), "operation": operation, "path": path}

    def _execute_registry_operation(self, operation: str, key: str = None,
                                     data: dict = None, query: str = None) -> dict[str, Any]:
        """
        Execute a registry operation for managing the institutional knowledge base.

        Args:
            operation: One of 'register', 'retrieve', 'list', 'search', 'update'
            key: Unique identifier for the registry entry
            data: Data to store (required for register/update operations)
            query: Search query for finding relevant past assessments

        Returns:
            Dictionary containing operation result and any registry data
        """
        try:
            logger.info(f"Registry operation: {operation}, key: {key}")

            registry = {}
            if os.path.exists(self.registry_file_path):
                try:
                    with open(self.registry_file_path, 'r', encoding='utf-8') as f:
                        registry = json.load(f)
                except json.JSONDecodeError:
                    registry = {}

            if operation == "register":
                if not key:
                    return {"success": False, "error": "Key required for register operation"}
                if not data:
                    return {"success": False, "error": "Data required for register operation"}
                registry[key] = {
                    **data,
                    "registered_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat()
                }
                with open(self.registry_file_path, 'w', encoding='utf-8') as f:
                    json.dump(registry, f, indent=2, default=str)
                return {"success": True, "message": f"Entry registered with key: {key}", "key": key}

            elif operation == "retrieve":
                if not key:
                    return {"success": False, "error": "Key required for retrieve operation"}
                if key in registry:
                    return {"success": True, "data": registry[key], "key": key}
                else:
                    return {"success": False, "error": f"Key not found: {key}", "key": key}

            elif operation == "list":
                entries = [{"key": k, "registered_at": v.get("registered_at", "unknown")}
                          for k, v in registry.items()]
                return {"success": True, "entries": entries, "total": len(entries)}

            elif operation == "search":
                if not query:
                    return {"success": False, "error": "Query required for search operation"}
                query_lower = query.lower()
                matching_entries = {}
                for k, v in registry.items():
                    entry_str = json.dumps(v).lower()
                    if query_lower in entry_str or query_lower in k.lower():
                        matching_entries[k] = v
                return {"success": True, "results": matching_entries, "query": query,
                        "total_matches": len(matching_entries)}

            elif operation == "update":
                if not key:
                    return {"success": False, "error": "Key required for update operation"}
                if not data:
                    return {"success": False, "error": "Data required for update operation"}
                if key in registry:
                    registry[key].update({**data, "last_updated": datetime.now().isoformat()})
                    with open(self.registry_file_path, 'w', encoding='utf-8') as f:
                        json.dump(registry, f, indent=2, default=str)
                    return {"success": True, "message": f"Entry updated: {key}", "key": key}
                else:
                    return {"success": False, "error": f"Key not found for update: {key}"}

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error(f"Registry operation failed: {e}")
            return {"success": False, "error": str(e), "operation": operation}

    def _process_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """
        Process a tool call and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Dictionary of input parameters for the tool

        Returns:
            JSON string containing the tool execution result
        """
        try:
            if tool_name == "web_search":
                query = tool_input.get("query", "")
                max_results = tool_input.get("max_results", self.search_max_results)
                result = self._execute_web_search(query, max_results)

            elif tool_name == "filesystem_server":
                operation = tool_input.get("operation", "")
                path = tool_input.get("path", "")
                content = tool_input.get("content")
                result = self._execute_filesystem_operation(operation, path, content)

            elif tool_name == "registry_server":
                operation = tool_input.get("operation", "")
                key = tool_input.get("key")
                data = tool_input.get("data")
                query = tool_input.get("query")
                result = self._execute_registry_operation(operation, key, data, query)

            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            return json.dumps(result, default=str)

        except Exception as e:
            logger.error(f"Tool call processing failed for {tool_name}: {e}")
            return json.dumps({"error": str(e), "tool": tool_name})

    async def run(self, task: str) -> str:
        """
        Execute the strategy opportunity assessment for a given task.

        This method orchestrates the full assessment workflow including:
        - Market sizing research and validation
        - Competitive landscape mapping
        - Strategic fit scoring
        - Risk identification and prioritization
        - Investment memo generation
        - Registry update with completed assessment

        Args:
            task: Description of the business opportunity to evaluate, including
                  any available context, claims, or specific questions to address

        Returns:
            Structured investment memo and recommendation as a formatted string

        Raises:
            anthropic.APIError: If the Anthropic API call fails
            ValueError: If the task is empty or invalid
        """
        if not task or not task.strip():
            raise ValueError("Task cannot be empty")

        logger.info(f"Starting opportunity assessment for task: {task[:100]}...")

        messages = [
            {
                "role": "user",
                "content": f"""Please conduct a comprehensive strategic opportunity assessment for the following:

{task}

Your assessment should follow this structured methodology:

1. MARKET ANALYSIS
   - Conduct web searches to validate market size claims (TAM/SAM/SOM)
   - Identify market growth trends and drivers
   - Assess market timing and maturity

2. COMPETITIVE LANDSCAPE
   - Map key competitors and their positioning
   - Identify differentiation opportunities and white space
   - Assess moat strength and defensibility

3. STRATEGIC FIT SCORING (0-10 scale)
   - Alignment with founder mission and portfolio
   - Resource requirements vs. available capabilities
   - Time-to-value and strategic leverage

4. RISK ASSESSMENT
   - Market risks (size, timing, adoption)
   - Execution risks (team, technology, operations)
   - Regulatory and compliance risks
   - Financial risks (capital requirements, unit economics)

5. INVESTMENT MEMO
   - Executive summary with clear recommendation (BUY/PASS/INVESTIGATE)
   - Supporting evidence and key assumptions
   - Critical success factors
   - Next steps and decision criteria

6. REGISTRY UPDATE
   - Save this assessment to the institutional knowledge registry
   - Note any patterns from similar past opportunities

Please search for relevant market data, save your assessment to the filesystem, and register it in the knowledge registry. If critical information is missing, clearly identify what is needed and why."""
            }
        ]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages
            )
            logger.info(f"Initial response received, stop_reason: {response.stop_reason}")

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error during initial call: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during initial API call: {e}")
            raise

        iteration_count = 0
        max_iterations = 20

        while response.stop_reason == "tool_use" and iteration_count < max_iterations:
            iteration_count += 1
            logger.info(f"Processing tool calls, iteration {iteration_count}")

            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input
                    tool_use_id = content_block.id

                    logger.info(f"Executing tool: {tool_name} with input keys: {list(tool_input.keys())}")

                    try:
                        tool_result = self._process_tool_call(tool_name, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": tool_result
                        })
                        logger.info(f"Tool {tool_name} executed successfully")
                    except Exception as e:
                        logger.error(f"Tool execution failed for {tool_name}: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps({"error": str(e), "tool": tool_name}),
                            "is_error": True
                        })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=messages
                )
                logger.info(f"Follow-up response received, stop_reason: {response.stop_reason}")

            except anthropic.APIError as e:
                logger.error(f"Anthropic API error during tool follow-up call: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during tool follow-up call: {e}")
                raise

        if iteration_count >= max_iterations:
            logger.warning(f"Reached maximum iterations ({max_iterations}) for tool calls")

        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        if not final_response:
            final_response = "Assessment completed but no text response was generated. Please check the registry and filesystem for saved results."

        logger.info(f"Assessment completed successfully after {iteration_count} tool call iterations")
        return final_response


async def main():
    """
    Main entry point for testing the StrategyOpportunityAgent.

    Demonstrates the agent's capability to evaluate a sample business opportunity.
    """
    try:
        agent = StrategyOpportunityAgent()

        sample_task = """
        Opportunity Brief: AI-Powered Legal Document Review Platform

        Overview: A SaaS platform that uses large language models to automate contract review,
        due diligence, and compliance checking for mid-market companies.

        Key Claims:
        - Total addressable market of $15B in legal tech
        - 60% cost reduction vs. traditional legal review
        - Target customers: companies with 100-1000 employees spending $500K+ annually on legal

        Current Status: Pre-seed, founding team of 2 (ex-BigLaw attorney + ML engineer)
        Seeking: $2M seed round

        Questions to Address:
        1. Is the $15B TAM claim credible?
        2. Who are the main competitors and how differentiated is this approach?
        3. What are the key risks we should be concerned about?
        4. Should we invest or pass?
        """

        result = await agent.run(sample_task)
        print("=" * 80)
        print("STRATEGY OPPORTUNITY ASSESSMENT RESULT")
        print("=" * 80)
        print(result)
        print("=" * 80)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())