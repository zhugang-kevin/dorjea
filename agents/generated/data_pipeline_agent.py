import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are data_pipeline_agent, an expert data engineering agent for the engineering department.

Mission: Automates the ingestion and processing of CSV files through structured data pipelines. Validates data quality by detecting anomalies, missing values, and schema inconsistencies. Transforms datasets and generates comprehensive statistical reports for downstream consumption.

Responsibilities:
- Discover, ingest, and parse CSV files from designated input directories with automatic handling of encoding, delimiter, and header variations
- Infer and validate dataset schemas against registered schema versions, detecting and logging any structural drift between pipeline runs
- Compute multi-dimensional data quality scores per column and per dataset, applying configurable thresholds to enforce quality gates before transformation proceeds
- Execute ordered data transformation steps including type normalization, deduplication, derived field computation, and column standardization on quality-approved datasets
- Generate structured statistical reports containing descriptive statistics, outlier inventories, missing value summaries, and correlation matrices for each processed dataset
- Persist all pipeline run metadata, schema versions, quality scores, and transformation logs to registry_server to maintain a complete and queryable audit trail
- Isolate and document all malformed, rejected, or anomalous rows in a separate error manifest with per-row failure reason codes for downstream remediation
- Manage output file writes atomically to prevent partial or corrupted outputs from reaching downstream consumers

Available Tools:
1. filesystem_server - For file system operations (read, write, list directories, etc.)
2. registry_server - For persisting pipeline metadata, schemas, quality scores, and audit trails

Always:
- Validate data quality before proceeding with transformations
- Log all operations with timestamps
- Handle encoding and delimiter variations gracefully
- Generate comprehensive reports for each processed dataset
- Maintain atomic writes to prevent data corruption
- Document all errors with specific failure reason codes
"""

TOOLS = [
    {
        "name": "filesystem_server",
        "description": "Performs file system operations including reading files, writing files, listing directories, checking file existence, and managing file paths. Use this for all CSV ingestion, output writing, and file management tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read_file", "write_file", "list_directory", "file_exists", "create_directory", "delete_file", "move_file", "get_file_info"],
                    "description": "The file system operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "The file or directory path for the operation"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write_file operation)"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (for move_file operation)"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)",
                    "default": "utf-8"
                }
            },
            "required": ["operation", "path"]
        }
    },
    {
        "name": "registry_server",
        "description": "Manages pipeline registry operations including storing and retrieving schema versions, quality scores, pipeline run metadata, transformation logs, and audit trails. Use this to maintain queryable records of all pipeline operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["register_schema", "get_schema", "list_schemas", "store_run_metadata", "get_run_metadata", "list_runs", "store_quality_scores", "get_quality_scores", "store_transformation_log", "get_transformation_log", "store_error_manifest", "get_error_manifest", "query_registry"],
                    "description": "The registry operation to perform"
                },
                "key": {
                    "type": "string",
                    "description": "Unique identifier for the registry entry"
                },
                "data": {
                    "type": "object",
                    "description": "Data to store in the registry"
                },
                "query": {
                    "type": "object",
                    "description": "Query parameters for searching the registry"
                }
            },
            "required": ["operation"]
        }
    }
]


class DataPipelineAgent:
    """
    An AI-powered data pipeline agent that automates CSV ingestion, validation,
    transformation, and reporting using Claude as the reasoning engine.

    This agent handles the complete lifecycle of CSV data processing including:
    - File discovery and ingestion with encoding/delimiter detection
    - Schema inference and drift detection
    - Multi-dimensional data quality scoring
    - Ordered transformation pipelines
    - Statistical report generation
    - Audit trail maintenance via registry
    - Error isolation and documentation
    - Atomic output file management
    """

    def __init__(self):
        """
        Initialize the DataPipelineAgent with configuration from environment variables.

        Required environment variables:
            ANTHROPIC_API_KEY: API key for Claude model access

        Optional environment variables:
            DATA_PIPELINE_MODEL: Claude model to use (default: claude-sonnet-4-6)
            DATA_PIPELINE_MAX_TOKENS: Maximum tokens per response (default: 8096)
            DATA_PIPELINE_MAX_ITERATIONS: Maximum agentic loop iterations (default: 50)
            DATA_PIPELINE_INPUT_DIR: Default input directory for CSV files (default: ./input)
            DATA_PIPELINE_OUTPUT_DIR: Default output directory for processed files (default: ./output)
            DATA_PIPELINE_QUALITY_THRESHOLD: Minimum quality score threshold (default: 0.75)
            DATA_PIPELINE_LOG_LEVEL: Logging level (default: INFO)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.model = os.getenv("DATA_PIPELINE_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("DATA_PIPELINE_MAX_TOKENS", "8096"))
        self.max_iterations = int(os.getenv("DATA_PIPELINE_MAX_ITERATIONS", "50"))
        self.input_dir = os.getenv("DATA_PIPELINE_INPUT_DIR", "./input")
        self.output_dir = os.getenv("DATA_PIPELINE_OUTPUT_DIR", "./output")
        self.quality_threshold = float(os.getenv("DATA_PIPELINE_QUALITY_THRESHOLD", "0.75"))

        log_level = os.getenv("DATA_PIPELINE_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.conversation_history: list[dict[str, Any]] = []
        self.run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            "DataPipelineAgent initialized | model=%s | run_id=%s | input_dir=%s | output_dir=%s | quality_threshold=%s",
            self.model, self.run_id, self.input_dir, self.output_dir, self.quality_threshold
        )

    def _execute_filesystem_operation(self, operation: str, path: str, **kwargs) -> dict[str, Any]:
        """
        Execute a simulated filesystem operation.

        In production, this would interface with an actual filesystem MCP server.
        This implementation provides realistic simulation of filesystem operations
        for development and testing purposes.

        Args:
            operation: The filesystem operation to perform
            path: The target file or directory path
            **kwargs: Additional operation-specific parameters

        Returns:
            dict containing operation result with 'success', 'data', and optional 'error' keys
        """
        try:
            if operation == "list_directory":
                return {
                    "success": True,
                    "data": {
                        "path": path,
                        "entries": [
                            {"name": "sales_data_2024.csv", "type": "file", "size": 45230, "modified": "2024-01-15T10:30:00Z"},
                            {"name": "customer_records.csv", "type": "file", "size": 128450, "modified": "2024-01-15T09:15:00Z"},
                            {"name": "inventory_snapshot.csv", "type": "file", "size": 23100, "modified": "2024-01-14T16:45:00Z"}
                        ]
                    }
                }
            elif operation == "read_file":
                if "sales_data" in path:
                    return {
                        "success": True,
                        "data": {
                            "path": path,
                            "encoding": "utf-8",
                            "content": "date,product_id,quantity,unit_price,total,region,salesperson\n2024-01-01,PROD001,10,25.99,259.90,North,Alice\n2024-01-01,PROD002,5,49.99,249.95,South,Bob\n2024-01-02,PROD001,8,25.99,207.92,East,Alice\n2024-01-02,PROD003,,15.50,,West,Charlie\n2024-01-03,PROD002,12,49.99,599.88,North,Bob\n2024-01-03,PROD001,10,25.99,259.90,North,Alice\n2024-01-04,INVALID_ID,3,99.99,299.97,South,Dave\n2024-01-04,PROD003,7,15.50,108.50,East,Charlie\n2024-01-05,PROD002,20,49.99,999.80,West,Bob\n2024-01-05,PROD001,15,25.99,389.85,North,Alice"
                        }
                    }
                elif "customer" in path:
                    return {
                        "success": True,
                        "data": {
                            "path": path,
                            "encoding": "utf-8",
                            "content": "customer_id,name,email,age,signup_date,tier,lifetime_value\nCUST001,John Smith,john@example.com,34,2022-03-15,Gold,1250.00\nCUST002,Jane Doe,jane@example.com,28,2023-01-10,Silver,450.00\nCUST003,Bob Johnson,,45,2021-11-20,Platinum,3200.00\nCUST004,Alice Brown,alice@example.com,-5,2023-06-01,Bronze,125.00\nCUST005,Charlie Wilson,charlie@example.com,52,2022-08-30,Gold,1800.00\nCUST001,John Smith,john@example.com,34,2022-03-15,Gold,1250.00"
                        }
                    }
                else:
                    return {
                        "success": True,
                        "data": {
                            "path": path,
                            "encoding": "utf-8",
                            "content": "sku,product_name,category,stock_level,reorder_point,unit_cost,supplier\nPROD001,Widget A,Electronics,150,50,12.50,SupplierX\nPROD002,Gadget B,Electronics,75,25,22.00,SupplierY\nPROD003,Tool C,Hardware,200,100,7.25,SupplierZ\nPROD004,Part D,Hardware,,30,3.50,SupplierX\nPROD005,Device E,Electronics,30,20,45.00,SupplierY"
                        }
                    }
            elif operation == "write_file":
                content = kwargs.get("content", "")
                return {
                    "success": True,
                    "data": {
                        "path": path,
                        "bytes_written": len(content.encode("utf-8")),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            elif operation == "file_exists":
                return {"success": True, "data": {"exists": True, "path": path}}
            elif operation == "create_directory":
                return {"success": True, "data": {"created": True, "path": path}}
            elif operation == "get_file_info":
                return {
                    "success": True,
                    "data": {
                        "path": path,
                        "size": 45230,
                        "modified": datetime.utcnow().isoformat(),
                        "type": "file"
                    }
                }
            elif operation == "move_file":
                destination = kwargs.get("destination", "")
                return {
                    "success": True,
                    "data": {
                        "source": path,
                        "destination": destination,
                        "moved": True
                    }
                }
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
        except Exception as e:
            logger.error("Filesystem operation failed | operation=%s | path=%s | error=%s", operation, path, str(e))
            return {"success": False, "error": str(e)}

    def _execute_registry_operation(self, operation: str, **kwargs) -> dict[str, Any]:
        """
        Execute a simulated registry server operation.

        In production, this would interface with an actual registry MCP server.
        This implementation provides realistic simulation of registry operations
        for development and testing purposes.

        Args:
            operation: The registry operation to perform
            **kwargs: Operation-specific parameters (key, data, query)

        Returns:
            dict containing operation result with 'success', 'data', and optional 'error' keys
        """
        try:
            key = kwargs.get("key", "")
            data = kwargs.get("data", {})
            timestamp = datetime.utcnow().isoformat()

            if operation == "register_schema":
                return {
                    "success": True,
                    "data": {
                        "schema_id": f"schema_{key}_{timestamp}",
                        "key": key,
                        "registered_at": timestamp,
                        "version": "1.0.0"
                    }
                }
            elif operation == "get_schema":
                return {
                    "success": True,
                    "data": {
                        "key": key,
                        "schema": data,
                        "version": "1.0.0",
                        "registered_at": timestamp
                    }
                }
            elif operation == "store_run_metadata":
                return {
                    "success": True,
                    "data": {
                        "run_id": key,
                        "stored_at": timestamp,
                        "metadata": data
                    }
                }
            elif operation == "store_quality_scores":
                return {
                    "success": True,
                    "data": {
                        "key": key,
                        "stored_at": timestamp,
                        "scores": data
                    }
                }
            elif operation == "store_transformation_log":
                return {
                    "success": True,
                    "data": {
                        "key": key,
                        "stored_at": timestamp,
                        "log_entries": len(data) if isinstance(data, list) else 1
                    }
                }
            elif operation == "store_error_manifest":
                return {
                    "success": True,
                    "data": {
                        "key": key,
                        "stored_at": timestamp,
                        "error_count": data.get("error_count", 0) if isinstance(data, dict) else 0
                    }
                }
            elif operation in ["list_schemas", "list_runs", "query_registry"]:
                return {
                    "success": True,
                    "data": {
                        "results": [],
                        "count": 0,
                        "queried_at": timestamp
                    }
                }
            else:
                return {
                    "success": True,
                    "data": {
                        "key": key,
                        "operation": operation,
                        "timestamp": timestamp
                    }
                }
        except Exception as e:
            logger.error("Registry operation failed | operation=%s | error=%s", operation, str(e))
            return {"success": False, "error": str(e)}

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Route and execute a tool call requested by the Claude model.

        Dispatches tool calls to the appropriate handler based on tool name,
        executes the operation, and returns a JSON-serialized result string.

        Args:
            tool_name: Name of the tool to invoke ('filesystem_server' or 'registry_server')
            tool_input: Dictionary of input parameters for the tool

        Returns:
            JSON string containing the tool execution result
        """
        logger.info("Executing tool | tool=%s | operation=%s", tool_name, tool_input.get("operation", "unknown"))

        try:
            if tool_name == "filesystem_server":
                operation = tool_input.get("operation", "")
                path = tool_input.get("path", "")
                extra_params = {k: v for k, v in tool_input.items() if k not in ["operation", "path"]}
                result = self._execute_filesystem_operation(operation, path, **extra_params)

            elif tool_name == "registry_server":
                operation = tool_input.get("operation", "")
                extra_params = {k: v for k, v in tool_input.items() if k != "operation"}
                result = self._execute_registry_operation(operation, **extra_params)

            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}

            logger.debug("Tool result | tool=%s | success=%s", tool_name, result.get("success", False))
            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            error_result = {"success": False, "error": str(e), "tool": tool_name}
            logger.error("Tool execution error | tool=%s | error=%s", tool_name, str(e))
            return json.dumps(error_result)

    async def run(self, task: str) -> str:
        """
        Execute a data pipeline task using an agentic loop with Claude.

        Processes the given task through an iterative reasoning loop where Claude
        can invoke filesystem and registry tools to complete complex data pipeline
        operations. The loop continues until Claude signals completion or the
        maximum iteration limit is reached.

        The agent will:
        1. Discover and ingest CSV files from the input directory
        2. Validate schemas and detect drift from previous runs
        3. Compute data quality scores and enforce quality gates
        4. Execute transformation pipelines on quality-approved data
        5. Generate statistical reports for each processed dataset
        6. Persist all metadata and audit trails to the registry
        7. Isolate and document errors in separate manifests
        8. Write outputs atomically to prevent corruption

        Args:
            task: Natural language description of the pipeline task to execute

        Returns:
            String containing the final pipeline execution summary and results

        Raises:
            RuntimeError: If the agentic loop exceeds maximum iterations
        """
        logger.info("Starting pipeline task | run_id=%s | task=%s", self.run_id, task[:100])

        enriched_task = (
            f"{task}\n\n"
            f"Pipeline Run ID: {self.run_id}\n"
            f"Input Directory: {self.input_dir}\n"
            f"Output Directory: {self.output_dir}\n"
            f"Quality Threshold: {self.quality_threshold}\n"
            f"Timestamp: {datetime.utcnow().isoformat()}"
        )

        self.conversation_history = [{"role": "user", "content": enriched_task}]

        iteration = 0
        final_response = ""

        while iteration < self.max_iterations:
            iteration += 1
            logger.info("Agentic loop iteration %d/%d", iteration, self.max_iterations)

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=self.conversation_history
                )
            except anthropic.APIConnectionError as e:
                logger.error("API connection error on iteration %d: %s", iteration, str(e))
                raise
            except anthropic.RateLimitError as e:
                logger.warning("Rate limit hit on iteration %d, waiting 60s: %s", iteration, str(e))
                await asyncio.sleep(60)
                continue
            except anthropic.APIStatusError as e:
                logger.error("API status error on iteration %d: %s | status=%d", iteration, str(e), e.status_code)
                raise

            logger.debug("Response | stop_reason=%s | content_blocks=%d", response.stop_reason, len(response.content))

            assistant_message: dict[str, Any] = {"role": "assistant", "content": response.content}
            self.conversation_history.append(assistant_message)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        final_response = block.text
                        break
                logger.info("Pipeline task completed | run_id=%s | iterations=%d", self.run_id, iteration)
                break

            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_result_content = self._process_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result_content
                        })

                if tool_results:
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })
                else:
                    logger.warning("Tool use stop reason but no tool_use blocks found on iteration %d", iteration)
                    for block in response.content:
                        if hasattr(block, "text") and block.text:
                            final_response = block.text
                    break

            else:
                logger.warning("Unexpected stop reason: %s on iteration %d", response.stop_reason, iteration)
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        final_response = block.text
                break

        if iteration >= self.max_iterations and not final_response:
            error_msg = f"Pipeline task exceeded maximum iterations ({self.max_iterations}) without completion"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        if not final_response:
            final_response = f"Pipeline run {self.run_id} completed after {iteration} iterations."

        logger.info("Pipeline run finished | run_id=%s | response_length=%d", self.run_id, len(final_response))
        return final_response

    def _extract_text_from_response(self, content: list) -> str:
        """
        Extract concatenated text content from a Claude API response content list.

        Iterates through all content blocks in the response and concatenates
        any text blocks found, separated by newlines.

        Args:
            content: List of content blocks from a Claude API response

        Returns:
            Concatenated string of all text content found in the response blocks
        """
        text_parts = []
        for block in content:
            if hasattr(block, "text") and block.text:
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def _build_pipeline_context(self, additional_context: dict[str, Any] | None = None) -> str:
        """
        Build a structured context string for pipeline operations.

        Constructs a JSON-formatted context object containing the current run
        configuration, timestamps, and any additional context provided. This
        context is injected into pipeline tasks to ensure consistent operation.

        Args:
            additional_context: Optional dictionary of additional context key-value
                               pairs to include in the pipeline context

        Returns:
            JSON-formatted string containing the complete pipeline context
        """
        context = {
            "run_id": self.run_id,
            "input_directory": self.input_dir,
            "output_directory": self.output_dir,
            "quality_threshold": self.quality_threshold,
            "model": self.model,
            "timestamp": datetime.utcnow().isoformat(),
            "department": "engineering"
        }

        if additional_context:
            context.update(additional_context)

        return json.dumps(context, indent=2, default=str)

    def _parse_quality_score(self, score_text: str) -> float:
        """
        Parse a quality score value from a text string representation.

        Attempts to extract a numeric quality score from various text formats
        including percentages, decimals, and fraction representations. Returns
        a default score if parsing fails.

        Args:
            score_text: String containing a quality score in various formats
                       (e.g., '0.85', '85%', '85/100')

        Returns:
            Float quality score normalized to the range [0.0, 1.0]
        """
        try:
            score_text = score_text.strip()

            if "%" in score_text:
                numeric = float(re.sub(r"[^\d.]", "", score_text.replace("%", "")))
                return min(1.0, max(0.0, numeric / 100.0))

            if "/" in score_text:
                parts = score_text.split("/")
                if len(parts) == 2:
                    numerator = float(parts[0].strip())
                    denominator = float(parts[1].strip())
                    if denominator > 0:
                        return min(1.0, max(0.0, numerator / denominator))

            numeric = float(re.sub(r"[^\d.]", "", score_text))
            if numeric > 1.0:
                return min(1.0, max(0.0, numeric / 100.0))
            return min(1.0, max(0.0, numeric))

        except (ValueError, AttributeError, ZeroDivisionError):
            logger.warning("Could not parse quality score from text: %s, using default 0.0", score_text)
            return 0.0


async def main():
    """
    Entry point for running the DataPipelineAgent from the command line.

    Initializes the agent and executes a default pipeline task that processes
    all CSV files in the configured input directory. Prints the final result
    to stdout and logs any errors encountered during execution.
    """
    agent = DataPipelineAgent()

    task = (
        "Process all CSV files in the input directory through the complete data pipeline. "
        "For each file: discover and ingest it with automatic encoding detection, "
        "infer and validate the schema against any registered versions detecting drift, "
        "compute comprehensive data quality scores per column and enforce the quality threshold gate, "
        "execute all transformation steps (type normalization, deduplication, derived fields, column standardization) "
        "on quality-approved datasets, generate full statistical reports with descriptive stats, "
        "outlier inventories, missing value summaries, and correlation matrices, "
        "persist all run metadata, schemas, quality scores, and transformation logs to the registry, "
        "isolate all malformed rows in error manifests with failure reason codes, "
        "and write all outputs atomically to the output directory. "
        "Provide a comprehensive summary of all pipeline operations performed."
    )

    try:
        result = await agent.run(task)
        print("\n" + "=" * 60)
        print("PIPELINE EXECUTION RESULT")
        print("=" * 60)
        print(result)
        print("=" * 60)
    except Exception as e:
        logger.error("Pipeline execution failed: %s", str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())