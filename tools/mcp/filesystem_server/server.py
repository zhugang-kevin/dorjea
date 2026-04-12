"""
server.py — Filesystem MCP server for safe file operations.
Runs as a separate process on port 8001.
All paths are restricted to the project root.
FastMCP 3.x API.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from fastmcp import FastMCP

PROJECT_ROOT = Path(os.getenv("AI_FACTORY_ROOT", "E:/Dorjea")).resolve()
mcp = FastMCP("dorjea-filesystem")


def _safe_path(relative_path: str) -> Path:
    """
    Resolve path and verify it stays inside project root.
    Raises ValueError if path tries to escape the project root.
    """
    full = (PROJECT_ROOT / relative_path).resolve()
    if not str(full).startswith(str(PROJECT_ROOT)):
        raise ValueError(f"Path '{relative_path}' is outside the project root.")
    return full


@mcp.tool()
def read_file(relative_path: str) -> str:
    """
    Read contents of a file relative to project root.
    Returns file contents as string or error message.
    """
    try:
        return _safe_path(relative_path).read_text(encoding="utf-8")
    except ValueError as e:
        return f"ERROR: {e}"
    except FileNotFoundError:
        return f"ERROR: File not found: {relative_path}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def write_file(relative_path: str, content: str) -> str:
    """
    Write content to a file relative to project root.
    Creates parent directories if they do not exist.
    Returns OK or error message.
    """
    try:
        path = _safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"OK: Written to {relative_path}"
    except ValueError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def file_exists(relative_path: str) -> str:
    """
    Check if a file exists relative to project root.
    Returns 'true' or 'false' as string.
    """
    try:
        return str(_safe_path(relative_path).exists()).lower()
    except ValueError as e:
        return f"ERROR: {e}"


@mcp.tool()
def list_directory(relative_path: str = ".") -> str:
    """
    List contents of a directory relative to project root.
    Returns JSON array of filenames or error message.
    """
    try:
        path = _safe_path(relative_path)
        if not path.is_dir():
            return f"ERROR: Not a directory: {relative_path}"
        items = [item.name for item in path.iterdir()]
        return json.dumps(items)
    except ValueError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def create_directory(relative_path: str) -> str:
    """
    Create a directory relative to project root.
    Creates all parent directories if needed.
    Returns OK or error message.
    """
    try:
        _safe_path(relative_path).mkdir(parents=True, exist_ok=True)
        return f"OK: Directory created: {relative_path}"
    except ValueError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"


if __name__ == "__main__":
    port = int(os.getenv("FILESYSTEM_MCP_PORT", "8001"))
    print(f"Starting Filesystem MCP Server on port {port}...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=port)
