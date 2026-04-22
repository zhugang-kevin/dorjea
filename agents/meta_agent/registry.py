"""
registry.py - Database operations for the agent registry.
All database reads and writes go through this file.
Never call the database directly from nodes or API.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./memory/aifactory.db")
USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

if not USE_POSTGRES:
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
else:
    DB_PATH = None

SQLITE_FALLBACK_PATH = os.getenv("SQLITE_FALLBACK_PATH", "./data/agentcore_registry.db")
JSON_FALLBACK_PATH = os.getenv(
    "REGISTRY_JSON_FALLBACK_PATH",
    "./data/agentcore_registry.json",
)


def _resolve_local_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _primary_sqlite_path() -> Optional[Path]:
    if DB_PATH is None:
        return None
    return _resolve_local_path(DB_PATH)


def _fallback_sqlite_path() -> Path:
    return _resolve_local_path(SQLITE_FALLBACK_PATH)


def _json_fallback_path() -> Path:
    return _resolve_local_path(JSON_FALLBACK_PATH)


def _ensure_sqlite_schema(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            mission TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            default_model TEXT,
            fallback_model TEXT,
            allowed_tools TEXT,
            token_budget INTEGER DEFAULT 10000,
            spec_yaml TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _ensure_json_registry_file() -> Path:
    path = _json_fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
    return path


def _load_json_agents() -> list[dict]:
    path = _ensure_json_registry_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _save_json_agents(agents: list[dict]) -> None:
    path = _ensure_json_registry_file()
    path.write_text(
        json.dumps(agents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _record_from_row(row: sqlite3.Row | dict | None) -> Optional[dict]:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    record = dict(row)
    allowed_tools = record.get("allowed_tools")
    if isinstance(allowed_tools, str):
        record["allowed_tools"] = [tool for tool in allowed_tools.split(",") if tool]
    elif allowed_tools is None:
        record["allowed_tools"] = []
    return record


def _json_record(record: dict) -> dict:
    payload = dict(record)
    payload["allowed_tools"] = list(payload.get("allowed_tools") or [])
    return payload


def _build_agent_record(
    name: str,
    mission: str,
    allowed_tools: list[str],
    default_model: str,
    fallback_model: str,
    token_budget: int,
    spec_yaml: str,
    department: str,
) -> dict:
    now = datetime.utcnow().isoformat()
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "mission": mission,
        "status": "active",
        "default_model": default_model,
        "fallback_model": fallback_model,
        "allowed_tools": list(allowed_tools),
        "token_budget": token_budget,
        "spec_yaml": spec_yaml,
        "department": department,
        "created_at": now,
        "updated_at": now,
    }


def _merge_agent_records(*collections: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for collection in collections:
        for item in collection:
            record = dict(item)
            name = record.get("name")
            if name:
                merged[name] = record
    return list(merged.values())


def _open_sqlite_connection(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _ensure_sqlite_schema(conn)
    conn.execute("SELECT 1").fetchone()
    conn.execute("PRAGMA quick_check").fetchone()
    return conn


def _get_sqlite_connection():
    last_error: Exception | None = None
    for candidate in (_primary_sqlite_path(), _fallback_sqlite_path()):
        if candidate is None:
            continue
        try:
            return _open_sqlite_connection(candidate)
        except sqlite3.Error as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise sqlite3.OperationalError("No SQLite registry path configured.")


def _fetchall(cursor):
    """Return rows as list of dicts for both SQLite and PostgreSQL."""
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    return [_record_from_row(row) for row in cursor.fetchall()]


def _fetchone(cursor):
    """Return one row as dict for both SQLite and PostgreSQL."""
    row = cursor.fetchone()
    if row is None:
        return None
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))
    return _record_from_row(row)


def _load_json_agents_filtered(status: str | None = None) -> list[dict]:
    agents = _load_json_agents()
    if status is None:
        return agents
    return [agent for agent in agents if agent.get("status") == status]


def _upsert_json_agent(record: dict) -> dict:
    agents = _load_json_agents()
    updated = False
    payload = _json_record(record)
    for idx, existing in enumerate(agents):
        if existing.get("name") == payload["name"]:
            agents[idx] = payload
            updated = True
            break
    if not updated:
        agents.append(payload)
    _save_json_agents(agents)
    return payload


def _update_json_status(agent_name: str, status: str) -> bool:
    agents = _load_json_agents()
    updated = False
    for agent in agents:
        if agent.get("name") == agent_name:
            agent["status"] = status
            agent["updated_at"] = datetime.utcnow().isoformat()
            updated = True
            break
    if updated:
        _save_json_agents(agents)
    return updated


def _enrich_agent(agent: dict) -> dict:
    if not agent:
        return agent
    spec_yaml = agent.get("spec_yaml", "")
    if spec_yaml:
        try:
            import yaml

            spec = yaml.safe_load(spec_yaml)
            if spec:
                for field in [
                    "department",
                    "responsibilities",
                    "non_responsibilities",
                    "escalation_triggers",
                    "memory_policy",
                    "retry_policy",
                ]:
                    if agent.get(field) in (None, "", "general") and spec.get(field):
                        agent[field] = spec[field]
        except Exception:
            pass
    return agent


def agent_exists(agent_name: str) -> bool:
    """
    Check if an agent with this name already exists in the registry.
    Returns True if found, False if not.
    """
    if USE_POSTGRES:
        try:
            conn = _get_sqlite_connection()
            conn.close()
        except Exception:
            pass
    else:
        with suppress(sqlite3.Error):
            conn = _get_sqlite_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM agents WHERE name = ? AND status != 'archived'",
                    (agent_name,),
                )
                result = cursor.fetchone()
                if result is not None:
                    return True
            finally:
                conn.close()
    return any(
        agent.get("name") == agent_name and agent.get("status") != "archived"
        for agent in _load_json_agents()
    )


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
    record = _build_agent_record(
        name=name,
        mission=mission,
        allowed_tools=allowed_tools,
        default_model=default_model,
        fallback_model=fallback_model,
        token_budget=token_budget,
        spec_yaml=spec_yaml,
        department=department,
    )
    if not USE_POSTGRES:
        try:
            conn = _get_sqlite_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO agents
                    (id, name, mission, status, default_model, fallback_model,
                     allowed_tools, token_budget, spec_yaml, created_at, updated_at)
                    VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["name"],
                        record["mission"],
                        record["default_model"],
                        record["fallback_model"],
                        ",".join(record["allowed_tools"]),
                        record["token_budget"],
                        record["spec_yaml"],
                        record["created_at"],
                        record["updated_at"],
                    ),
                )
                conn.commit()
                return {"success": True, "agent_id": record["id"], "error": None}
            finally:
                conn.close()
        except sqlite3.IntegrityError as exc:
            return {"success": False, "agent_id": None, "error": str(exc)}
        except sqlite3.Error:
            pass
    try:
        _upsert_json_agent(record)
        return {"success": True, "agent_id": record["id"], "error": None}
    except Exception as exc:
        return {"success": False, "agent_id": None, "error": str(exc)}


def get_agent(agent_name: str) -> Optional[dict]:
    """
    Retrieve a single agent by name.
    Returns dict of agent fields or None if not found.
    """
    agent: Optional[dict] = None
    if not USE_POSTGRES:
        with suppress(sqlite3.Error):
            conn = _get_sqlite_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM agents WHERE name = ?",
                    (agent_name,),
                )
                agent = _fetchone(cursor)
            finally:
                conn.close()
    if agent is None:
        for item in _load_json_agents():
            if item.get("name") == agent_name:
                agent = dict(item)
                break
    if agent is None:
        return None
    return _enrich_agent(agent)


def list_agents(status: str = "active") -> list[dict]:
    """
    List all agents with the given status.
    Returns list of agent dicts.
    """
    sqlite_agents: list[dict] = []
    if not USE_POSTGRES:
        with suppress(sqlite3.Error):
            conn = _get_sqlite_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM agents WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
                sqlite_agents = _fetchall(cursor)
            finally:
                conn.close()
    json_agents = _load_json_agents_filtered(status=status)
    merged = _merge_agent_records(sqlite_agents, json_agents)
    merged.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return [_enrich_agent(agent) for agent in merged]


def update_agent_status(agent_name: str, status: str) -> bool:
    """
    Update the status of an agent in the registry.
    Returns True on success, False on failure.
    """
    allowed_statuses = {"active", "idle", "frozen", "requires_review", "archived"}
    if status not in allowed_statuses:
        return False
    updated = False
    if not USE_POSTGRES:
        with suppress(sqlite3.Error):
            conn = _get_sqlite_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE agents SET status = ?, updated_at = ? WHERE name = ?",
                    (status, datetime.utcnow().isoformat(), agent_name),
                )
                conn.commit()
                updated = cursor.rowcount > 0
            finally:
                conn.close()
    json_updated = _update_json_status(agent_name, status)
    return updated or json_updated
