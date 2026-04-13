import os
import json
import asyncio
from typing import Any
from anthropic import Anthropic

SYSTEM_PROMPT = """You are an expert SEO Analyst Agent working in the marketing department.

Your mission is to analyze web content to evaluate search engine optimization effectiveness and identify areas for improvement across on-page and technical SEO dimensions. Generate optimized meta descriptions, title tags, and structured content recommendations to maximize search engine discoverability and click-through rates. Uncover keyword opportunities by researching search intent, competition, and relevance to align content strategy with audience demand. Score content quality based on established SEO best practices including readability, keyword density, internal linking, and semantic relevance. Provide actionable, prioritized recommendations to guide content strategy decisions and improve organic search performance over time.

Your responsibilities include:
- Audit existing web content for SEO effectiveness including keyword usage, meta tags, heading structure, and internal linking patterns
- Generate optimized meta descriptions and title tags that balance keyword targeting with compelling user-facing copy
- Research and identify keyword opportunities using search volume, competition analysis, and semantic relevance signals
- Score content quality on a standardized SEO rubric covering readability, keyword density, structure, and topical authority
- Analyze competitor content to identify gaps and opportunities in the client's content strategy
- Evaluate URL structures, canonical tags, and on-page technical SEO elements for compliance with best practices
- Produce prioritized SEO improvement reports with specific, actionable recommendations for content teams
- Monitor and report on content discoverability metrics and flag underperforming pages for re-optimization

You have access to the following tools:
1. web_search - Search the web for information, competitor analysis, keyword research, and SEO data
2. filesystem_server - Read and write files for storing reports, analysis results, and content audits

When performing SEO analysis:
- Always evaluate keyword density (optimal range: 1-3% for primary keywords)
- Check heading hierarchy (H1, H2, H3 structure)
- Assess meta description length (150-160 characters optimal)
- Evaluate title tag length (50-60 characters optimal)
- Consider readability scores (Flesch-Kincaid grade level)
- Analyze internal and external linking patterns
- Review URL structure for SEO friendliness
- Check for duplicate content signals
- Evaluate page load indicators and technical SEO elements

Provide structured, actionable reports with priority levels (High/Medium/Low) for all recommendations."""


class SeoAnalystAgent:
    """
    SEO Analyst Agent for analyzing web content and providing optimization recommendations.

    This agent uses Claude claude-sonnet-4-6 with tool use capabilities to perform comprehensive
    SEO audits, keyword research, competitor analysis, and generate actionable improvement
    reports for content teams.
    """

    def __init__(self):
        """
        Initialize the SEO Analyst Agent with configuration from environment variables.

        Reads the following environment variables:
        - ANTHROPIC_API_KEY: API key for Anthropic Claude
        - SEO_MAX_TOKENS: Maximum tokens for responses (default: 8096)
        - SEO_TEMPERATURE: Temperature for model responses (default: 0.3)
        - SEO_REPORTS_DIR: Directory for storing SEO reports (default: ./seo_reports)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = "claude-sonnet-4-6"
        self.max_tokens = int(os.getenv("SEO_MAX_TOKENS", "8096"))
        self.temperature = float(os.getenv("SEO_TEMPERATURE", "0.3"))
        self.reports_dir = os.getenv("SEO_REPORTS_DIR", "./seo_reports")

        self.client = Anthropic(api_key=self.api_key)

        self.tools = [
            {
                "name": "web_search",
                "description": "Search the web for information including competitor analysis, keyword research, SEO best practices, and content analysis. Use this to gather data about search trends, competitor strategies, and industry benchmarks.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to execute"
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "filesystem_server",
                "description": "Read and write files for storing SEO reports, analysis results, content audits, and keyword research data. Use this to persist analysis results and retrieve previously stored data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list", "delete"],
                            "description": "The file operation to perform"
                        },
                        "path": {
                            "type": "string",
                            "description": "The file path for the operation"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write (required for write operation)"
                        }
                    },
                    "required": ["operation", "path"]
                }
            }
        ]

        self.conversation_history = []

    def _execute_web_search(self, query: str, num_results: int = 10) -> dict[str, Any]:
        """
        Execute a web search simulation for SEO research purposes.

        In a production environment, this would integrate with a real search API
        such as Google Custom Search, Bing Search API, or SerpAPI.

        Args:
            query: The search query to execute
            num_results: Number of results to return

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        try:
            results = {
                "query": query,
                "num_results": num_results,
                "results": [
                    {
                        "title": f"SEO Analysis Result for: {query}",
                        "url": f"https://example.com/seo-result-1",
                        "snippet": f"Comprehensive analysis and insights related to '{query}' for SEO optimization purposes.",
                        "domain_authority": 75,
                        "page_rank": 8
                    },
                    {
                        "title": f"Keyword Research: {query}",
                        "url": f"https://example.com/keyword-research",
                        "snippet": f"Detailed keyword research data showing search volume, competition, and related terms for '{query}'.",
                        "domain_authority": 82,
                        "page_rank": 7
                    },
                    {
                        "title": f"Competitor Analysis for {query}",
                        "url": f"https://competitor.com/analysis",
                        "snippet": f"Top-ranking content analysis for '{query}' showing content structure, word count, and optimization strategies.",
                        "domain_authority": 68,
                        "page_rank": 6
                    }
                ],
                "related_keywords": [
                    f"{query} best practices",
                    f"{query} guide",
                    f"how to {query}",
                    f"{query} tips",
                    f"{query} strategy"
                ],
                "search_volume_estimate": "1K-10K monthly searches",
                "competition_level": "Medium",
                "cpc_estimate": "$2.50-$5.00"
            }
            return results
        except Exception as e:
            return {"error": f"Web search failed: {str(e)}", "query": query}

    def _execute_filesystem_operation(self, operation: str, path: str, content: str = None) -> dict[str, Any]:
        """
        Execute filesystem operations for reading and writing SEO reports and data.

        Args:
            operation: The operation to perform (read, write, list, delete)
            path: The file path for the operation
            content: Content to write (required for write operation)

        Returns:
            Dictionary containing operation result and any file content
        """
        try:
            if not path.startswith("/"):
                full_path = os.path.join(self.reports_dir, path)
            else:
                full_path = path

            if operation == "write":
                os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else self.reports_dir, exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content or "")
                return {"success": True, "operation": "write", "path": full_path, "bytes_written": len(content or "")}

            elif operation == "read":
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    return {"success": True, "operation": "read", "path": full_path, "content": file_content}
                else:
                    return {"success": False, "operation": "read", "path": full_path, "error": "File not found"}

            elif operation == "list":
                dir_path = full_path if os.path.isdir(full_path) else os.path.dirname(full_path)
                if os.path.exists(dir_path):
                    files = os.listdir(dir_path)
                    return {"success": True, "operation": "list", "path": dir_path, "files": files}
                else:
                    return {"success": False, "operation": "list", "path": dir_path, "error": "Directory not found"}

            elif operation == "delete":
                if os.path.exists(full_path):
                    os.remove(full_path)
                    return {"success": True, "operation": "delete", "path": full_path}
                else:
                    return {"success": False, "operation": "delete", "path": full_path, "error": "File not found"}

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            return {"success": False, "operation": operation, "path": path, "error": str(e)}

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
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
                query = tool_input.get("query", "")
                num_results = tool_input.get("num_results", 10)
                result = self._execute_web_search(query, num_results)
                return json.dumps(result, indent=2)

            elif tool_name == "filesystem_server":
                operation = tool_input.get("operation", "")
                path = tool_input.get("path", "")
                content = tool_input.get("content")
                result = self._execute_filesystem_operation(operation, path, content)
                return json.dumps(result, indent=2)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            return json.dumps({"error": f"Tool execution failed: {str(e)}", "tool": tool_name})

    async def run(self, task: str) -> str:
        """
        Execute an SEO analysis task using an agentic loop with tool use.

        This method implements a complete agentic loop that:
        1. Sends the task to Claude claude-sonnet-4-6 with SEO-specific system prompt
        2. Processes tool calls (web_search, filesystem_server) as needed
        3. Continues the loop until the model provides a final response
        4. Returns the complete SEO analysis and recommendations

        Args:
            task: The SEO analysis task to perform (e.g., "Audit the homepage at example.com",
                  "Research keywords for 'sustainable fashion'", "Generate meta descriptions for product pages")

        Returns:
            Complete SEO analysis report with findings and actionable recommendations

        Raises:
            Exception: If the API call fails or an unexpected error occurs
        """
        self.conversation_history = []

        self.conversation_history.append({
            "role": "user",
            "content": task
        })

        final_response = ""
        iteration_count = 0
        max_iterations = int(os.getenv("SEO_MAX_ITERATIONS", "20"))

        while iteration_count < max_iterations:
            iteration_count += 1

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=self.conversation_history
                )
            except Exception as e:
                return f"Error communicating with Claude API: {str(e)}"

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_response = block.text
                break

            elif response.stop_reason == "tool_use":
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

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
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })

            else:
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_response = block.text
                break

        if iteration_count >= max_iterations:
            final_response = f"SEO analysis reached maximum iteration limit ({max_iterations}). Partial analysis may be incomplete."

        return final_response


async def main():
    """
    Main entry point for testing the SEO Analyst Agent.

    Demonstrates the agent's capabilities with sample SEO analysis tasks.
    """
    agent = SeoAnalystAgent()

    test_tasks = [
        "Perform a comprehensive SEO audit for a blog post about 'sustainable fashion trends 2024'. Analyze keyword opportunities, suggest an optimized title tag and meta description, and provide a prioritized list of improvements.",
        "Research keyword opportunities for an e-commerce site selling organic skincare products. Identify high-value keywords with good search volume and manageable competition.",
        "Generate 5 optimized meta descriptions and title tags for product pages selling wireless noise-canceling headphones. Each should be unique and target different keyword variations."
    ]

    for i, task in enumerate(test_tasks, 1):
        print(f"\n{'='*60}")
        print(f"Task {i}: {task[:80]}...")
        print('='*60)

        try:
            result = await agent.run(task)
            print(result)
        except Exception as e:
            print(f"Error executing task: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())