"""
registry.py — Database operations for the agent registry.
All database reads and writes go through this file.
Never call the database directly from nodes or API.
"""
from __future__ import annotations
import os
import uuid
import sqlite3
from datetime import datetime
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./memory/aifactory.db")
USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

if not USE_POSTGRES:
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
else:
    DB_PATH = None


def _get_connection():
    """
    Return a database connection — SQLite for dev, PostgreSQL for prod.
    """
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _fetchall(cursor):
    """Return rows as list of dicts for both SQLite and PostgreSQL."""
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    return [dict(row) for row in cursor.fetchall()]


def _fetchone(cursor):
    """Return one row as dict for both SQLite and PostgreSQL."""
    row = cursor.fetchone()
    if row is None:
        return None
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))
    return dict(row)


def agent_exists(agent_name: str) -> bool:
    """
    Check if an agent with this name already exists in the registry.
    Returns True if found, False if not.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM agents WHERE name = ? AND status != 'archived'",
            (agent_name,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False


def register_agent(
    name: str,
    mission: str,
    allowed_tools: list[str],
    default_model: str,
    fallback_model: str,
    token_budget: int,
    spec_yaml: str,
    department: str = "general",
) -> dict:
    """
    Insert a new agent into the registry with status ACTIVE.
    Returns dict with keys: success, agent_id, error.
    """
    try:
        agent_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agents
            (id, name, mission, status, default_model, fallback_model,
             allowed_tools, token_budget, spec_yaml, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_id, name, mission, default_model, fallback_model,
            ",".join(allowed_tools), token_budget, spec_yaml, now, now
        ))
        conn.commit()
        conn.close()
        return {"success": True, "agent_id": agent_id, "error": None}
    except Exception as e:
        return {"success": False, "agent_id": None, "error": str(e)}


def _enrich_agent(agent: dict) -> dict:
    if not agent:
        return agent
    spec_yaml = agent.get("spec_yaml", "")
    if spec_yaml:
        try:
            import yaml
            spec = yaml.safe_load(spec_yaml)
            if spec:
                for field in ["department", "responsibilities", "non_responsibilities",
                              "escalation_triggers", "memory_policy", "retry_policy"]:
                    if agent.get(field) in (None, "", "general") and spec.get(field):
                        agent[field] = spec[field]
        except Exception:
            pass
    return agent

def get_agent(agent_name: str) -> Optional[dict]:
    """
    Retrieve a single agent by name.
    Returns dict of agent fields or None if not found.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agents WHERE name = ?",
            (agent_name,)
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return dict(row)
    except Exception:
        return None


def list_agents(status: str = "active") -> list[dict]:
    """
    List all agents with the given status.
    Returns list of agent dicts.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agents WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        rows = _fetchall(cursor)
        conn.close()
        return [_enrich_agent(row) for row in rows]
    except Exception:
        return []


def update_agent_status(agent_name: str, status: str) -> bool:
    """
    Update the status of an agent in the registry.
    Returns True on success, False on failure.
    """
    allowed_statuses = {"active", "idle", "frozen", "requires_review", "archived"}
    if status not in allowed_statuses:
        return False
    try:
        now = datetime.utcnow().isoformat()
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE agents SET status = ?, updated_at = ? WHERE name = ?",
            (status, now, agent_name)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False
