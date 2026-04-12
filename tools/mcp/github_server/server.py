"""
server.py — GitHub MCP server for Git operations.
Runs as a separate process on port 8003.
Handles branch creation and file commits only.
FastMCP 3.x API.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from fastmcp import FastMCP

PROJECT_ROOT = Path(os.getenv("AI_FACTORY_ROOT", "E:/Dorjea")).resolve()
mcp = FastMCP("dorjea-github")


def _run_git(args: list[str]) -> dict:
    """
    Run a git command in the project root.
    Returns dict with stdout, stderr, success keys.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Git command timed out.", "success": False}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "success": False}


@mcp.tool()
def create_branch(branch_name: str) -> str:
    """
    Create a new Git branch from current HEAD.
    Returns OK or error message.
    """
    if not branch_name or "/" in branch_name:
        return "ERROR: Invalid branch name."
    result = _run_git(["checkout", "-b", branch_name])
    if result["success"]:
        return f"OK: Branch '{branch_name}' created."
    return f"ERROR: {result['stderr']}"


@mcp.tool()
def commit_files(message: str, file_paths: str = ".") -> str:
    """
    Stage and commit files to the current branch.
    file_paths: space-separated list of paths to stage, or '.' for all.
    Returns OK with commit hash or error message.
    """
    if not message or len(message.strip()) < 5:
        return "ERROR: Commit message must be at least 5 characters."
    paths = file_paths.strip().split() if file_paths.strip() != "." else ["."]
    add_result = _run_git(["add"] + paths)
    if not add_result["success"]:
        return f"ERROR staging files: {add_result['stderr']}"
    commit_result = _run_git(["commit", "-m", message.strip()])
    if not commit_result["success"]:
        if "nothing to commit" in commit_result["stdout"]:
            return "OK: Nothing to commit."
        return f"ERROR committing: {commit_result['stderr']}"
    return f"OK: Committed — {commit_result['stdout']}"


@mcp.tool()
def get_current_branch() -> str:
    """
    Return the name of the current Git branch.
    """
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if result["success"]:
        return result["stdout"]
    return f"ERROR: {result['stderr']}"


@mcp.tool()
def get_status() -> str:
    """
    Return the current Git status of the project.
    """
    result = _run_git(["status", "--short"])
    if result["success"]:
        return result["stdout"] or "Clean — nothing to commit."
    return f"ERROR: {result['stderr']}"


if __name__ == "__main__":
    port = int(os.getenv("GITHUB_MCP_PORT", "8003"))
    print(f"Starting GitHub MCP Server on port {port}...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=port)
