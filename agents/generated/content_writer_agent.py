"""
Content Writer Agent - SEO-optimized blog post creation agent for the marketing department.
"""

import asyncio
import json
import os
import re
from typing import Any

import anthropic


class ContentWriterAgent:
    """
    An AI agent specialized in creating high-quality, SEO-optimized blog posts.

    This agent researches keywords, analyzes competitor content, structures articles
    for readability and search engine performance, and delivers content drafts to
    the filesystem for review and publication workflows.
    """

    def __init__(self):
        """
        Initialize the ContentWriterAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            BRAVE_SEARCH_API_KEY: API key for Brave Search (web search tool)
            CONTENT_OUTPUT_DIR: Directory path for saving content drafts
            BRAND_VOICE: Description of brand voice and tone guidelines
            TARGET_AUDIENCE: Description of the target audience
            CONTENT_LANGUAGE: Language for content (default: 'en')
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        self.output_dir = os.getenv("CONTENT_OUTPUT_DIR", "./content_drafts")
        self.brand_voice = os.getenv(
            "BRAND_VOICE",
            "Professional, informative, and engaging with a conversational tone"
        )
        self.target_audience = os.getenv(
            "TARGET_AUDIENCE",
            "Marketing professionals and business owners"
        )
        self.content_language = os.getenv("CONTENT_LANGUAGE", "en")
        self.model = "claude-sonnet-4-6"

        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.tools = [
            {
                "name": "web_search",
                "description": (
                    "Search the web for information about keywords, competitor content, "
                    "SEO trends, and topic research. Use this to gather data for content creation."
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
            },
            {
                "name": "filesystem_server",
                "description": (
                    "Read from and write to the filesystem. Use this to save content drafts, "
                    "read brand guidelines, and manage content files."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list", "create_directory"],
                            "description": "The filesystem operation to perform"
                        },
                        "path": {
                            "type": "string",
                            "description": "The file or directory path"
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

        self.system_prompt = f"""You are an expert content writer and SEO specialist working for the marketing department.

Your mission is to create high-quality, SEO-optimized blog posts that drive organic traffic and align with brand goals.

Brand Voice: {self.brand_voice}
Target Audience: {self.target_audience}
Content Language: {self.content_language}

Your responsibilities include:
1. Research and identify high-value target keywords and search intent
2. Produce well-structured, SEO-optimized blog posts with appropriate headings, meta descriptions, and keyword placement
3. Analyze competitor content and top-ranking articles to inform content strategy
4. Ensure all content adheres to brand voice, tone guidelines, and editorial standards
5. Optimize content readability using clear sentence structure and logical flow
6. Incorporate internal and external linking strategies
7. Deliver content drafts to the filesystem for review and publication
8. Apply SEO best practices including title tags, alt text recommendations, and schema markup suggestions

When creating content:
- Always start with keyword research using web_search
- Structure articles with H1, H2, H3 headings appropriately
- Include a compelling meta description (150-160 characters)
- Aim for optimal keyword density (1-2% for primary keywords)
- Suggest internal and external links where appropriate
- Include alt text recommendations for images
- Provide schema markup suggestions when relevant
- Save final drafts to the filesystem using filesystem_server

Output directory for content: {self.output_dir}
"""

    def _execute_web_search(self, query: str, num_results: int = 5) -> dict[str, Any]:
        """
        Execute a web search using the Brave Search API.

        Args:
            query: The search query string
            num_results: Number of results to return

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        try:
            import urllib.parse
            import urllib.request

            encoded_query = urllib.parse.quote(query)
            url = f"https://api.search.brave.com/res/v1/web/search?q={encoded_query}&count={num_results}"

            request = urllib.request.Request(url)
            request.add_header("Accept", "application/json")
            request.add_header("Accept-Encoding", "gzip")
            request.add_header("X-Subscription-Token", self.brave_api_key or "")

            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read()

                import gzip
                if response.info().get("Content-Encoding") == "gzip":
                    response_data = gzip.decompress(response_data)

                data = json.loads(response_data.decode("utf-8"))

            results = []
            if "web" in data and "results" in data["web"]:
                for item in data["web"]["results"][:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                        "age": item.get("age", "")
                    })

            return {
                "query": query,
                "results": results,
                "total_results": len(results)
            }

        except Exception as e:
            return {
                "query": query,
                "results": [],
                "error": str(e),
                "total_results": 0
            }

    def _execute_filesystem_operation(
        self,
        operation: str,
        path: str,
        content: str = None
    ) -> dict[str, Any]:
        """
        Execute a filesystem operation (read, write, list, create_directory).

        Args:
            operation: The operation type ('read', 'write', 'list', 'create_directory')
            path: The file or directory path
            content: Content to write (required for write operation)

        Returns:
            Dictionary containing operation result and status
        """
        try:
            if operation == "create_directory":
                os.makedirs(path, exist_ok=True)
                return {"success": True, "message": f"Directory created: {path}"}

            elif operation == "write":
                if content is None:
                    return {"success": False, "error": "Content is required for write operation"}

                dir_path = os.path.dirname(path)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

                return {
                    "success": True,
                    "message": f"File written successfully: {path}",
                    "bytes_written": len(content.encode("utf-8"))
                }

            elif operation == "read":
                if not os.path.exists(path):
                    return {"success": False, "error": f"File not found: {path}"}

                with open(path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                return {
                    "success": True,
                    "content": file_content,
                    "path": path
                }

            elif operation == "list":
                if not os.path.exists(path):
                    return {"success": False, "error": f"Directory not found: {path}"}

                items = []
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    items.append({
                        "name": item,
                        "type": "directory" if os.path.isdir(item_path) else "file",
                        "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                    })

                return {
                    "success": True,
                    "path": path,
                    "items": items,
                    "count": len(items)
                }

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
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
                num_results = tool_input.get("num_results", 5)
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
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})

    async def run(self, task: str) -> str:
        """
        Execute a content writing task using the AI agent with tool use.

        This method orchestrates the full content creation workflow:
        1. Analyzes the task and identifies content requirements
        2. Researches keywords and competitor content via web search
        3. Creates SEO-optimized content following brand guidelines
        4. Saves the content draft to the filesystem
        5. Returns a summary of the completed work

        Args:
            task: Description of the content to create (e.g., "Write a blog post about
                  email marketing best practices for small businesses")

        Returns:
            String containing the agent's final response with content summary,
            file location, and SEO recommendations

        Raises:
            anthropic.APIError: If there's an issue with the Anthropic API
        """
        messages = [
            {
                "role": "user",
                "content": task
            }
        ]

        final_response = ""

        try:
            while True:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=messages
                )

                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response = block.text
                    break

                elif response.stop_reason == "tool_use":
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_result = self._process_tool_call(
                                block.name,
                                block.input
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result
                            })

                    if tool_results:
                        messages.append({
                            "role": "user",
                            "content": tool_results
                        })

                else:
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response = block.text
                    break

        except anthropic.APIConnectionError as e:
            final_response = f"Connection error while communicating with AI service: {str(e)}"
        except anthropic.RateLimitError as e:
            final_response = f"Rate limit exceeded. Please try again later: {str(e)}"
        except anthropic.APIStatusError as e:
            final_response = f"API error occurred (status {e.status_code}): {str(e)}"
        except Exception as e:
            final_response = f"Unexpected error during content creation: {str(e)}"

        return final_response


async def main():
    """
    Main entry point for running the ContentWriterAgent.

    Demonstrates the agent's capabilities by executing a sample content creation task.
    """
    agent = ContentWriterAgent()

    task = os.getenv(
        "CONTENT_TASK",
        (
            "Write a comprehensive, SEO-optimized blog post about '10 Email Marketing "
            "Best Practices for Small Businesses in 2024'. The post should target "
            "small business owners looking to improve their email marketing ROI. "
            "Research current trends, analyze top-ranking content, and create a "
            "well-structured article with proper headings, meta description, and "
            "keyword optimization. Save the draft to the content output directory."
        )
    )

    print(f"Starting ContentWriterAgent with task:\n{task}\n")
    print("=" * 60)

    result = await agent.run(task)

    print("\nAgent Response:")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())