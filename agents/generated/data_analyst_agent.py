import os
import json
import asyncio
import logging
import statistics
import math
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisConfig(BaseModel):
    """Configuration model for the data analyst agent."""

    model: str = Field(default="claude-sonnet-4-6")
    max_tokens: int = Field(default=8096)
    department: str = Field(default="research")
    output_dir: str = Field(default="./analysis_outputs")
    max_iterations: int = Field(default=10)


class DataAnalystAgent:
    """
    Data Analyst Agent that processes raw datasets to generate comprehensive
    statistical summaries and identify meaningful patterns within the data.

    This agent analyzes trends, correlations, and anomalies to surface actionable
    insights that drive informed decision-making. It produces structured insight
    reports that communicate findings clearly to stakeholders across the organization.

    The agent operates with rigor and transparency, documenting methodology and
    assumptions to ensure reproducibility and trust in its outputs.
    """

    def __init__(self):
        """
        Initialize the DataAnalystAgent with configuration from environment variables.

        Environment Variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude (required)
            AGENT_MODEL: Model to use for analysis (default: claude-sonnet-4-6)
            AGENT_MAX_TOKENS: Maximum tokens for responses (default: 8096)
            AGENT_DEPARTMENT: Department identifier (default: research)
            AGENT_OUTPUT_DIR: Directory for storing analysis outputs (default: ./analysis_outputs)
            AGENT_MAX_ITERATIONS: Maximum agentic loop iterations (default: 10)
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.client = anthropic.Anthropic(api_key=api_key)

        self.config = AnalysisConfig(
            model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8096")),
            department=os.getenv("AGENT_DEPARTMENT", "research"),
            output_dir=os.getenv("AGENT_OUTPUT_DIR", "./analysis_outputs"),
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "10")),
        )

        self.tools = self._define_tools()
        self.system_prompt = self._build_system_prompt()

        logger.info(
            f"DataAnalystAgent initialized with model={self.config.model}, "
            f"department={self.config.department}"
        )

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for the data analyst agent.

        Returns:
            str: The complete system prompt defining agent behavior and responsibilities.
        """
        return f"""You are a rigorous Data Analyst Agent operating in the {self.config.department} department.

Your mission is to process raw datasets to generate comprehensive statistical summaries and identify meaningful patterns within the data. You analyze trends, correlations, and anomalies to surface actionable insights that drive informed decision-making.

## Core Responsibilities

1. **Data Ingestion & Validation**: Ingest and validate raw datasets from supported sources, checking for completeness, consistency, and formatting issues before analysis begins.

2. **Descriptive Statistics**: Compute descriptive statistics including mean, median, variance, standard deviation, and distribution profiles for all relevant numeric fields.

3. **Anomaly Detection**: Identify and flag statistical anomalies, outliers, and data quality issues that may affect the integrity of analysis outputs.

4. **Trend Analysis**: Detect trends over time and across dimensions using appropriate statistical methods such as moving averages, regression, and seasonality decomposition.

5. **Correlation Analysis**: Analyze correlations and relationships between variables to surface potential causal or associative patterns worth investigating further.

6. **Report Generation**: Generate structured insight reports in a standardized format that includes:
   - Executive Summary
   - Methodology
   - Key Findings
   - Visualization References
   - Recommended Next Steps

7. **Artifact Storage**: Store completed reports and intermediate analysis artifacts to the filesystem using consistent naming conventions for traceability.

8. **External Enrichment**: Query the web or registry as needed to enrich analysis with external benchmarks, definitions, or domain context relevant to the dataset.

## Operating Principles

- Always validate data quality before proceeding with analysis
- Document all assumptions and methodology decisions
- Use statistical rigor in all computations
- Flag uncertainty and limitations clearly
- Ensure all outputs are reproducible and traceable
- Use ISO 8601 timestamps in all artifacts
- Follow naming convention: `{{agent_name}}_{{task_type}}_{{timestamp}}.{{ext}}`

## Current Date/Time
{datetime.utcnow().isoformat()}Z

## Output Directory
{self.config.output_dir}

Always think step-by-step. When analyzing data, first validate it, then compute statistics, then identify patterns, then generate the report, and finally store all artifacts."""

    def _define_tools(self) -> list[dict[str, Any]]:
        """
        Define the tools available to the data analyst agent.

        Returns:
            list[dict]: List of tool definitions for filesystem, registry, and web search operations.
        """
        return [
            {
                "name": "read_file",
                "description": "Read the contents of a file from the filesystem. Use this to ingest datasets, configuration files, or previously stored analysis artifacts.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The absolute or relative path to the file to read.",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)",
                            "default": "utf-8",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to a file on the filesystem. Use this to store analysis reports, intermediate artifacts, and computed statistics. Creates directories as needed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The absolute or relative path where the file should be written.",
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file.",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)",
                            "default": "utf-8",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": "List the contents of a directory on the filesystem. Use this to discover available datasets or previously generated reports.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The directory path to list.",
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "compute_statistics",
                "description": "Compute comprehensive descriptive statistics for a list of numeric values. Returns mean, median, mode, variance, standard deviation, min, max, range, quartiles, IQR, skewness, and outlier detection.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "values": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "List of numeric values to analyze.",
                        },
                        "field_name": {
                            "type": "string",
                            "description": "Name of the field being analyzed (for labeling purposes).",
                        },
                        "outlier_threshold": {
                            "type": "number",
                            "description": "IQR multiplier for outlier detection (default: 1.5)",
                            "default": 1.5,
                        },
                    },
                    "required": ["values", "field_name"],
                },
            },
            {
                "name": "compute_correlation",
                "description": "Compute Pearson correlation coefficient between two numeric series. Returns correlation coefficient, interpretation, and statistical significance assessment.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "series_a": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "First numeric series.",
                        },
                        "series_b": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Second numeric series.",
                        },
                        "label_a": {
                            "type": "string",
                            "description": "Label for the first series.",
                        },
                        "label_b": {
                            "type": "string",
                            "description": "Label for the second series.",
                        },
                    },
                    "required": ["series_a", "series_b", "label_a", "label_b"],
                },
            },
            {
                "name": "compute_moving_average",
                "description": "Compute simple moving average for a time series to detect trends. Returns the smoothed series and trend direction.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "values": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Time-ordered numeric values.",
                        },
                        "window_size": {
                            "type": "integer",
                            "description": "Number of periods for the moving average window.",
                        },
                        "field_name": {
                            "type": "string",
                            "description": "Name of the field being analyzed.",
                        },
                    },
                    "required": ["values", "window_size", "field_name"],
                },
            },
            {
                "name": "web_search",
                "description": "Search the web for external benchmarks, domain definitions, industry standards, or contextual information to enrich the analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to execute.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "registry_lookup",
                "description": "Look up definitions, schemas, metadata, or domain context from the internal registry to enrich analysis with organizational knowledge.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "The registry key or identifier to look up.",
                        },
                        "registry_type": {
                            "type": "string",
                            "description": "Type of registry to query: 'schema', 'metadata', 'benchmark', 'definition'",
                            "enum": ["schema", "metadata", "benchmark", "definition"],
                        },
                    },
                    "required": ["key", "registry_type"],
                },
            },
            {
                "name": "validate_dataset",
                "description": "Validate a dataset represented as a list of records (dicts). Checks for missing values, type consistency, duplicate records, and structural integrity.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "records": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of data records to validate.",
                        },
                        "expected_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of field names expected in each record.",
                        },
                        "dataset_name": {
                            "type": "string",
                            "description": "Name identifier for the dataset being validated.",
                        },
                    },
                    "required": ["records", "dataset_name"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Execute a tool call and return the result as a string.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Dictionary of input parameters for the tool.

        Returns:
            str: JSON-encoded result of the tool execution.
        """
        try:
            if tool_name == "read_file":
                return self._tool_read_file(**tool_input)
            elif tool_name == "write_file":
                return self._tool_write_file(**tool_input)
            elif tool_name == "list_directory":
                return self._tool_list_directory(**tool_input)
            elif tool_name == "compute_statistics":
                return self._tool_compute_statistics(**tool_input)
            elif tool_name == "compute_correlation":
                return self._tool_compute_correlation(**tool_input)
            elif tool_name == "compute_moving_average":
                return self._tool_compute_moving_average(**tool_input)
            elif tool_name == "web_search":
                return self._tool_web_search(**tool_input)
            elif tool_name == "registry_lookup":
                return self._tool_registry_lookup(**tool_input)
            elif tool_name == "validate_dataset":
                return self._tool_validate_dataset(**tool_input)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return json.dumps({"error": str(e), "tool": tool_name})

    def _tool_read_file(self, path: str, encoding: str = "utf-8") -> str:
        """
        Read a file from the filesystem.

        Args:
            path: Path to the file to read.
            encoding: File encoding (default: utf-8).

        Returns:
            str: JSON result with file content or error.
        """
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            return json.dumps(
                {
                    "success": True,
                    "path": path,
                    "content": content,
                    "size_bytes": len(content.encode(encoding)),
                }
            )
        except FileNotFoundError:
            return json.dumps({"success": False, "error": f"File not found: {path}"})
        except PermissionError:
            return json.dumps(
                {"success": False, "error": f"Permission denied reading: {path}"}
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> str:
        """
        Write content to a file on the filesystem, creating directories as needed.

        Args:
            path: Path where the file should be written.
            content: Content to write to the file.
            encoding: File encoding (default: utf-8).

        Returns:
            str: JSON result indicating success or failure.
        """
        try:
            import os

            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            with open(path, "w", encoding=encoding) as f:
                f.write(content)

            return json.dumps(
                {
                    "success": True,
                    "path": path,
                    "bytes_written": len(content.encode(encoding)),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )
        except PermissionError:
            return json.dumps(
                {"success": False, "error": f"Permission denied writing to: {path}"}
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_list_directory(self, path: str) -> str:
        """
        List the contents of a directory.

        Args:
            path: Directory path to list.

        Returns:
            str: JSON result with directory listing or error.
        """
        try:
            import os

            if not os.path.exists(path):
                return json.dumps(
                    {"success": False, "error": f"Directory not found: {path}"}
                )

            entries = []
            for entry in os.scandir(path):
                entries.append(
                    {
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size_bytes": entry.stat().st_size if entry.is_file() else None,
                        "modified": datetime.fromtimestamp(
                            entry.stat().st_mtime
                        ).isoformat(),
                    }
                )

            return json.dumps(
                {
                    "success": True,
                    "path": path,
                    "entry_count": len(entries),
                    "entries": entries,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_compute_statistics(
        self,
        values: list[float],
        field_name: str,
        outlier_threshold: float = 1.5,
    ) -> str:
        """
        Compute comprehensive descriptive statistics for a list of numeric values.

        Args:
            values: List of numeric values to analyze.
            field_name: Name of the field being analyzed.
            outlier_threshold: IQR multiplier for outlier detection (default: 1.5).

        Returns:
            str: JSON result with complete statistical summary.
        """
        try:
            if not values:
                return json.dumps(
                    {"success": False, "error": "Empty values list provided"}
                )

            clean_values = [float(v) for v in values if v is not None]
            n = len(clean_values)

            if n == 0:
                return json.dumps(
                    {"success": False, "error": "No non-null values to analyze"}
                )

            sorted_vals = sorted(clean_values)

            mean_val = statistics.mean(clean_values)
            median_val = statistics.median(clean_values)
            variance_val = statistics.variance(clean_values) if n > 1 else 0.0
            stdev_val = statistics.stdev(clean_values) if n > 1 else 0.0
            min_val = min(clean_values)
            max_val = max(clean_values)
            range_val = max_val - min_val

            q1_idx = n // 4
            q3_idx = (3 * n) // 4
            q1 = sorted_vals[q1_idx]
            q3 = sorted_vals[q3_idx]
            iqr = q3 - q1

            lower_fence = q1 - outlier_threshold * iqr
            upper_fence = q3 + outlier_threshold * iqr
            outliers = [v for v in clean_values if v < lower_fence or v > upper_fence]

            try:
                mode_val = statistics.mode(clean_values)
            except statistics.StatisticsError:
                mode_val = None

            n_float = float(n)
            if stdev_val > 0:
                skewness = (
                    (n_float / ((n_float - 1) * (n_float - 2)))
                    * sum(((v - mean_val) / stdev_val) ** 3 for v in clean_values)
                    if n > 2
                    else 0.0
                )
            else:
                skewness = 0.0

            cv = (stdev_val / mean_val * 100) if mean_val != 0 else None

            return json.dumps(
                {
                    "success": True,
                    "field_name": field_name,
                    "n": n,
                    "null_count": len(values) - n,
                    "mean": round(mean_val, 6),
                    "median": round(median_val, 6),
                    "mode": mode_val,
                    "variance": round(variance_val, 6),
                    "std_dev": round(stdev_val, 6),
                    "coefficient_of_variation_pct": (
                        round(cv, 4) if cv is not None else None
                    ),
                    "min": min_val,
                    "max": max_val,
                    "range": round(range_val, 6),
                    "q1": q1,
                    "q3": q3,
                    "iqr": round(iqr, 6),
                    "lower_fence": round(lower_fence, 6),
                    "upper_fence": round(upper_fence, 6),
                    "outlier_count": len(outliers),
                    "outliers": outliers[:20],
                    "skewness": round(skewness, 6),
                    "skewness_interpretation": (
                        "approximately symmetric"
                        if abs(skewness) < 0.5
                        else (
                            "moderately skewed"
                            if abs(skewness) < 1.0
                            else "highly skewed"
                        )
                    ),
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_compute_correlation(
        self,
        series_a: list[float],
        series_b: list[float],
        label_a: str,
        label_b: str,
    ) -> str:
        """
        Compute Pearson correlation coefficient between two numeric series.

        Args:
            series_a: First numeric series.
            series_b: Second numeric series.
            label_a: Label for the first series.
            label_b: Label for the second series.

        Returns:
            str: JSON result with correlation coefficient and interpretation.
        """
        try:
            if len(series_a) != len(series_b):
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Series length mismatch: {len(series_a)} vs {len(series_b)}",
                    }
                )

            pairs = [
                (float(a), float(b))
                for a, b in zip(series_a, series_b)
                if a is not None and b is not None
            ]

            if len(pairs) < 3:
                return json.dumps(
                    {
                        "success": False,
                        "error": "Insufficient data points for correlation (need >= 3)",
                    }
                )

            n = len(pairs)
            vals_a = [p[0] for p in pairs]
            vals_b = [p[1] for p in pairs]

            mean_a = statistics.mean(vals_a)
            mean_b = statistics.mean(vals_b)

            numerator = sum(
                (a - mean_a) * (b - mean_b) for a, b in zip(vals_a, vals_b)
            )
            denom_a = math.sqrt(sum((a - mean_a) ** 2 for a in vals_a))
            denom_b = math.sqrt(sum((b - mean_b) ** 2 for b in vals_b))

            if denom_a == 0 or denom_b == 0:
                return json.dumps(
                    {
                        "success": False,
                        "error": "Cannot compute correlation: one or both series have zero variance",
                    }
                )

            r = numerator / (denom_a * denom_b)
            r = max(-1.0, min(1.0, r))

            abs_r = abs(r)
            if abs_r >= 0.9:
                strength = "very strong"
            elif abs_r >= 0.7:
                strength = "strong"
            elif abs_r >= 0.5:
                strength = "moderate"
            elif abs_r >= 0.3:
                strength = "weak"
            else:
                strength = "negligible"

            direction = "positive" if r > 0 else "negative" if r < 0 else "none"

            t_stat = r * math.sqrt(n - 2) / math.sqrt(1 - r**2) if abs(r) < 1 else float("inf")

            return json.dumps(
                {
                    "success": True,
                    "label_a": label_a,
                    "label_b": label_b,
                    "n_pairs": n,
                    "pearson_r": round(r, 6),
                    "r_squared": round(r**2, 6),
                    "strength": strength,
                    "direction": direction,
                    "interpretation": f"{strength} {direction} correlation between {label_a} and {label_b}",
                    "t_statistic": round(t_stat, 4),
                    "degrees_of_freedom": n - 2,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_compute_moving_average(
        self, values: list[float], window_size: int, field_name: str
    ) -> str:
        """
        Compute simple moving average for trend detection.

        Args:
            values: Time-ordered numeric values.
            window_size: Number of periods for the moving average window.
            field_name: Name of the field being analyzed.

        Returns:
            str: JSON result with smoothed series and trend analysis.
        """
        try:
            if not values:
                return json.dumps(
                    {"success": False, "error": "Empty values list provided"}
                )

            if window_size < 2:
                return json.dumps(
                    {"success": False, "error": "Window size must be >= 2"}
                )

            clean_values = [float(v) for v in values if v is not None]
            n = len(clean_values)

            if window_size > n:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Window size ({window_size}) exceeds data length ({n})",
                    }
                )

            sma = []
            for i in range(window_size - 1, n):
                window = clean_values[i - window_size + 1 : i + 1]
                sma.append(round(statistics.mean(window), 6))

            if len(sma) >= 2:
                first_half_mean = statistics.mean(sma[: len(sma) // 2])
                second_half_mean = statistics.mean(sma[len(sma) // 2 :])
                trend_pct = (
                    ((second_half_mean - first_half_mean) / abs(first_half_mean) * 100)
                    if first_half_mean != 0
                    else 0.0
                )

                if trend_pct > 5:
                    trend_direction = "upward"
                elif trend_pct < -5:
                    trend_direction = "downward"
                else:
                    trend_direction = "stable"
            else:
                trend_pct = 0.0
                trend_direction = "insufficient data"

            return json.dumps(
                {
                    "success": True,
                    "field_name": field_name,
                    "window_size": window_size,
                    "original_length": n,
                    "sma_length": len(sma),
                    "sma_values": sma,
                    "trend_direction": trend_direction,
                    "trend_change_pct": round(trend_pct, 4),
                    "sma_min": min(sma) if sma else None,
                    "sma_max": max(sma) if sma else None,
                    "sma_mean": round(statistics.mean(sma), 6) if sma else None,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_web_search(self, query: str, max_results: int = 5) -> str:
        """
        Simulate a web search for external benchmarks and domain context.

        In production, this would integrate with a real search API.
        Returns structured search result metadata for the agent to reason about.

        Args:
            query: The search query to execute.
            max_results: Maximum number of results to return.

        Returns:
            str: JSON result with search metadata and guidance.
        """
        try:
            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "note": "Web search capability is available. In production deployment, integrate with a search API (e.g., Brave Search, SerpAPI, or Bing Search API) using SEARCH_API_KEY environment variable.",
                    "suggested_sources": [
                        "Industry reports and whitepapers",
                        "Academic databases (Google Scholar, PubMed)",
                        "Government statistical agencies (BLS, Census Bureau)",
                        "Domain-specific registries and standards bodies",
                    ],
                    "max_results_requested": max_results,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_registry_lookup(self, key: str, registry_type: str) -> str:
        """
        Look up definitions, schemas, or benchmarks from the internal registry.

        Args:
            key: The registry key or identifier to look up.
            registry_type: Type of registry to query (schema, metadata, benchmark, definition).

        Returns:
            str: JSON result with registry entry or guidance.
        """
        try:
            registry_path = os.getenv(
                "REGISTRY_PATH", "./registry"
            )
            registry_file = os.path.join(
                registry_path, registry_type, f"{key}.json"
            )

            if os.path.exists(registry_file):
                with open(registry_file, "r") as f:
                    entry = json.load(f)
                return json.dumps(
                    {
                        "success": True,
                        "key": key,
                        "registry_type": registry_type,
                        "entry": entry,
                    }
                )
            else:
                return json.dumps(
                    {
                        "success": True,
                        "key": key,
                        "registry_type": registry_type,
                        "found": False,
                        "note": f"No registry entry found for key '{key}' in '{registry_type}' registry. "
                        f"Configure REGISTRY_PATH environment variable to point to your registry directory.",
                        "expected_path": registry_file,
                    }
                )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _tool_validate_dataset(
        self,
        records: list[dict],
        dataset_name: str,
        expected_fields: list[str] | None = None,
    ) -> str:
        """
        Validate a dataset for completeness, consistency, and structural integrity.

        Args:
            records: List of data records to validate.
            dataset_name: Name identifier for the dataset.
            expected_fields: Optional list of expected field names.

        Returns:
            str: JSON result with validation report.
        """
        try:
            if not records:
                return json.dumps(