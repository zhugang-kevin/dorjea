import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Any

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeManagementAgent:
    """
    Agent for organizing and maintaining company documents within a structured
    internal knowledge base. Handles employee queries, audits documentation,
    and continuously improves knowledge organization.
    """

    def __init__(self):
        """
        Initialize the KnowledgeManagementAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            KNOWLEDGE_BASE_PATH: Path to the knowledge base directory
            MAX_TOKENS: Maximum tokens for model responses (default: 8096)
            MODEL_NAME: Claude model to use (default: claude-sonnet-4-6)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.knowledge_base_path = os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "8096"))
        self.model_name = os.getenv("MODEL_NAME", "claude-sonnet-4-6")
        self.department = os.getenv("DEPARTMENT", "operations")

        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.tools = [
            {
                "name": "read_file",
                "description": "Read the contents of a file from the knowledge base filesystem. Use this to retrieve document content, metadata, or configuration files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The file path to read from the knowledge base"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or update content to a file in the knowledge base filesystem. Use this to create new documents, update existing ones, or save metadata.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The file path to write to"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file"
                        }
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "list_directory",
                "description": "List files and directories in a given path within the knowledge base. Use this to explore the knowledge base structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The directory path to list"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "search_files",
                "description": "Search for files matching a pattern or containing specific content in the knowledge base.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or pattern to find relevant files"
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory path to search within (default: root knowledge base)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_registry_entry",
                "description": "Retrieve a registry entry for a document or category from the knowledge base registry. The registry tracks document metadata, versions, and relationships.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "The registry key or document identifier to look up"
                        }
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "update_registry",
                "description": "Update or create a registry entry for a document. Use this to track document metadata, categorization, version history, and relationships.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "The registry key or document identifier"
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Metadata object containing document information such as category, tags, version, last_updated, author, status"
                        }
                    },
                    "required": ["key", "metadata"]
                }
            },
            {
                "name": "web_search",
                "description": "Search the web for current external information to supplement internal knowledge base content when internal resources are insufficient.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant external information"
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of search results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

        self.system_prompt = f"""You are the Knowledge Management Agent for the {self.department} department. 
Your mission is to organize and maintain company documents within a structured internal knowledge base, 
ensuring information is consistently accurate, well-categorized, and easily accessible to all employees.

Your core responsibilities:
1. Ingest, categorize, and index new documents using consistent taxonomy and metadata standards
2. Respond to employee queries by retrieving and synthesizing relevant content
3. Identify outdated, duplicate, or conflicting documents and flag them for review
4. Monitor knowledge base coverage and surface gaps where documentation is missing
5. Maintain document version history and ensure current versions are accessible
6. Perform periodic audits to optimize navigation, tagging, and cross-linking
7. Use web search to supplement internal knowledge when internal resources are insufficient
8. Generate usage and coverage reports for operations leadership

When handling tasks:
- Always check the knowledge base first before using web search
- Maintain consistent taxonomy: use categories like [HR, IT, Finance, Operations, Legal, Product, Engineering]
- Tag documents with relevant keywords for discoverability
- Track version history with timestamps and change summaries
- Flag documents older than 1 year for review
- Create cross-links between related documents
- Provide structured, actionable responses

Knowledge base path: {self.knowledge_base_path}
Current date: {datetime.now().strftime('%Y-%m-%d')}"""

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Execute a tool call and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Dictionary of input parameters for the tool

        Returns:
            String result of the tool execution
        """
        try:
            if tool_name == "read_file":
                return self._read_file(tool_input["path"])
            elif tool_name == "write_file":
                return self._write_file(tool_input["path"], tool_input["content"])
            elif tool_name == "list_directory":
                return self._list_directory(tool_input["path"])
            elif tool_name == "search_files":
                path = tool_input.get("path", self.knowledge_base_path)
                return self._search_files(tool_input["query"], path)
            elif tool_name == "get_registry_entry":
                return self._get_registry_entry(tool_input["key"])
            elif tool_name == "update_registry":
                return self._update_registry(tool_input["key"], tool_input["metadata"])
            elif tool_name == "web_search":
                num_results = tool_input.get("num_results", 5)
                return self._web_search(tool_input["query"], num_results)
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return f"Error executing {tool_name}: {str(e)}"

    def _read_file(self, path: str) -> str:
        """
        Read a file from the filesystem.

        Args:
            path: File path to read

        Returns:
            File contents as string or error message
        """
        try:
            full_path = path if os.path.isabs(path) else os.path.join(self.knowledge_base_path, path)
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"File contents of {path}:\n{content}"
        except FileNotFoundError:
            return f"File not found: {path}"
        except PermissionError:
            return f"Permission denied reading file: {path}"
        except Exception as e:
            return f"Error reading file {path}: {str(e)}"

    def _write_file(self, path: str, content: str) -> str:
        """
        Write content to a file in the filesystem.

        Args:
            path: File path to write to
            content: Content to write

        Returns:
            Success or error message
        """
        try:
            full_path = path if os.path.isabs(path) else os.path.join(self.knowledge_base_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {path}"
        except PermissionError:
            return f"Permission denied writing to file: {path}"
        except Exception as e:
            return f"Error writing file {path}: {str(e)}"

    def _list_directory(self, path: str) -> str:
        """
        List contents of a directory.

        Args:
            path: Directory path to list

        Returns:
            Directory listing as formatted string
        """
        try:
            full_path = path if os.path.isabs(path) else os.path.join(self.knowledge_base_path, path)
            if not os.path.exists(full_path):
                return f"Directory not found: {path}"

            items = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                if os.path.isdir(item_path):
                    items.append(f"[DIR]  {item}/")
                else:
                    size = os.path.getsize(item_path)
                    modified = datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M')
                    items.append(f"[FILE] {item} ({size} bytes, modified: {modified})")

            if not items:
                return f"Directory {path} is empty"

            return f"Contents of {path}:\n" + "\n".join(sorted(items))
        except PermissionError:
            return f"Permission denied accessing directory: {path}"
        except Exception as e:
            return f"Error listing directory {path}: {str(e)}"

    def _search_files(self, query: str, path: str) -> str:
        """
        Search for files matching a query within a directory.

        Args:
            query: Search query to match against filenames and content
            path: Directory path to search within

        Returns:
            Search results as formatted string
        """
        try:
            full_path = path if os.path.isabs(path) else os.path.join(self.knowledge_base_path, path)
            if not os.path.exists(full_path):
                return f"Search path not found: {path}"

            results = []
            query_lower = query.lower()

            for root, dirs, files in os.walk(full_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, self.knowledge_base_path)

                    if query_lower in filename.lower():
                        results.append(f"[NAME MATCH] {relative_path}")
                        continue

                    try:
                        if filename.endswith(('.txt', '.md', '.json', '.yaml', '.yml', '.csv')):
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            if query_lower in content.lower():
                                snippet_idx = content.lower().find(query_lower)
                                start = max(0, snippet_idx - 50)
                                end = min(len(content), snippet_idx + 100)
                                snippet = content[start:end].replace('\n', ' ')
                                results.append(f"[CONTENT MATCH] {relative_path}\n  ...{snippet}...")
                    except Exception:
                        pass

            if not results:
                return f"No files found matching '{query}' in {path}"

            return f"Search results for '{query}':\n" + "\n".join(results[:20])
        except Exception as e:
            return f"Error searching files: {str(e)}"

    def _get_registry_entry(self, key: str) -> str:
        """
        Retrieve a registry entry from the knowledge base registry file.

        Args:
            key: Registry key to look up

        Returns:
            Registry entry as formatted string or not found message
        """
        try:
            registry_path = os.path.join(self.knowledge_base_path, ".registry", "index.json")
            if not os.path.exists(registry_path):
                return f"Registry not initialized. No entry found for key: {key}"

            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            if key in registry:
                entry = registry[key]
                return f"Registry entry for '{key}':\n{json.dumps(entry, indent=2)}"
            else:
                return f"No registry entry found for key: {key}"
        except json.JSONDecodeError:
            return f"Error: Registry file is corrupted or invalid JSON"
        except Exception as e:
            return f"Error retrieving registry entry for {key}: {str(e)}"

    def _update_registry(self, key: str, metadata: dict[str, Any]) -> str:
        """
        Update or create a registry entry in the knowledge base registry.

        Args:
            key: Registry key to update
            metadata: Metadata dictionary to store

        Returns:
            Success or error message
        """
        try:
            registry_dir = os.path.join(self.knowledge_base_path, ".registry")
            os.makedirs(registry_dir, exist_ok=True)
            registry_path = os.path.join(registry_dir, "index.json")

            registry = {}
            if os.path.exists(registry_path):
                try:
                    with open(registry_path, 'r', encoding='utf-8') as f:
                        registry = json.load(f)
                except json.JSONDecodeError:
                    registry = {}

            metadata["last_registry_update"] = datetime.now().isoformat()
            registry[key] = metadata

            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2)

            return f"Successfully updated registry entry for '{key}'"
        except Exception as e:
            return f"Error updating registry for {key}: {str(e)}"

    def _web_search(self, query: str, num_results: int = 5) -> str:
        """
        Perform a web search to supplement internal knowledge.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            Search results as formatted string
        """
        try:
            search_results = [
                {
                    "title": f"Search Result {i+1} for: {query}",
                    "url": f"https://example.com/result-{i+1}",
                    "snippet": f"This is a simulated search result for '{query}'. In production, this would connect to a real search API like Google Custom Search, Bing, or DuckDuckGo."
                }
                for i in range(min(num_results, 3))
            ]

            formatted_results = [f"Web search results for '{query}':"]
            for i, result in enumerate(search_results, 1):
                formatted_results.append(
                    f"\n{i}. {result['title']}\n   URL: {result['url']}\n   {result['snippet']}"
                )

            formatted_results.append(
                "\nNote: Web search is simulated. Configure SEARCH_API_KEY and SEARCH_ENGINE_ID "
                "environment variables to enable real web search functionality."
            )

            return "\n".join(formatted_results)
        except Exception as e:
            return f"Error performing web search for '{query}': {str(e)}"

    async def run(self, task: str) -> str:
        """
        Execute a knowledge management task using the Claude model with tool use.

        This method implements an agentic loop that:
        1. Sends the task to Claude with available tools
        2. Executes any tool calls Claude requests
        3. Returns tool results to Claude
        4. Continues until Claude provides a final response

        Args:
            task: The task or query to process

        Returns:
            Final response string from the agent after completing the task
        """
        logger.info(f"Starting knowledge management task: {task[:100]}...")

        messages = [
            {"role": "user", "content": task}
        ]

        max_iterations = 20
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"Agent iteration {iteration}")

                try:
                    response = self.client.messages.create(
                        model=self.model_name,
                        max_tokens=self.max_tokens,
                        system=self.system_prompt,
                        tools=self.tools,
                        messages=messages
                    )
                except anthropic.APIConnectionError as e:
                    logger.error(f"API connection error: {e}")
                    return f"Error: Failed to connect to Anthropic API - {str(e)}"
                except anthropic.RateLimitError as e:
                    logger.error(f"Rate limit error: {e}")
                    return f"Error: API rate limit exceeded - {str(e)}"
                except anthropic.APIStatusError as e:
                    logger.error(f"API status error: {e}")
                    return f"Error: API returned status error {e.status_code} - {str(e)}"

                logger.info(f"Response stop reason: {response.stop_reason}")

                if response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            final_text += block.text

                    logger.info("Task completed successfully")
                    return final_text if final_text else "Task completed with no text response."

                if response.stop_reason == "tool_use":
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            logger.info(f"Executing tool: {block.name} with inputs: {json.dumps(block.input)[:200]}")

                            tool_result = self._execute_tool(block.name, block.input)
                            logger.info(f"Tool result preview: {tool_result[:200]}...")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result
                            })

                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })
                else:
                    logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            final_text += block.text
                    return final_text if final_text else f"Task ended with stop reason: {response.stop_reason}"

            logger.warning(f"Reached maximum iterations ({max_iterations})")
            return f"Task processing reached maximum iteration limit ({max_iterations}). The task may require simplification or breaking into smaller steps."

        except Exception as e:
            logger.error(f"Unexpected error in agent run: {e}", exc_info=True)
            return f"Error: Unexpected failure during task execution - {str(e)}"


async def main():
    """
    Main entry point for running the KnowledgeManagementAgent.
    Demonstrates basic usage with sample tasks.
    """
    agent = KnowledgeManagementAgent()

    sample_tasks = [
        "List all documents in the knowledge base and provide a summary of the current structure.",
        "Search for any HR-related documents and check if they are properly categorized.",
        "Generate a coverage report showing which departments have documentation and which are missing.",
    ]

    task = sample_tasks[0]
    print(f"\nExecuting task: {task}\n{'='*60}")

    result = await agent.run(task)
    print(f"\nResult:\n{result}")


if __name__ == "__main__":
    asyncio.run(main())