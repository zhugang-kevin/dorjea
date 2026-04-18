from __future__ import annotations
import json
import os
import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/memory", tags=["memory"])

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "memory", "agent_memory.jsonl")

VALID_TYPES = {
    "task_result", "key_learning", "customer_preference",
    "decision_pattern", "error_log", "best_practice", "context_data",
}

MEMORY_TYPE_DEFS = [
    {"id": "task_result",          "name": "Task Result",          "description": "Output and outcome from a completed task",       "icon": "\u2705"},
    {"id": "key_learning",         "name": "Key Learning",         "description": "Important insight or lesson learned",            "icon": "\U0001f4a1"},
    {"id": "customer_preference",  "name": "Customer Preference",  "description": "User preference or behavioral pattern",          "icon": "\U0001f464"},
    {"id": "decision_pattern",     "name": "Decision Pattern",     "description": "A decision rule that proved effective",          "icon": "\U0001f3af"},
    {"id": "error_log",            "name": "Error Log",            "description": "A mistake made and how it was corrected",        "icon": "\u26a0\ufe0f"},
    {"id": "best_practice",        "name": "Best Practice",        "description": "A technique that consistently works well",       "icon": "\u2b50"},
    {"id": "context_data",         "name": "Context Data",         "description": "Background information for future tasks",        "icon": "\U0001f4cb"},
]


# ── helpers ────────────────────────────────────────────────────────────────

def _ensure_dir() -> None:
    """Create memory directory if it does not exist."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)


def _load_all() -> list[dict]:
    """Load every record from agent_memory.jsonl."""
    if not os.path.exists(MEMORY_FILE):
        return []
    records: list[dict] = []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _save_all(records: list[dict]) -> None:
    """Overwrite agent_memory.jsonl with the given records."""
    _ensure_dir()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _append(record: dict) -> None:
    """Append a single record to agent_memory.jsonl."""
    _ensure_dir()
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _new_id() -> str:
    """Generate a unique memory_id."""
    return "mem_" + secrets.token_hex(8)


# ── request models ─────────────────────────────────────────────────────────

class AddMemoryRequest(BaseModel):
    """Payload for adding a new memory."""
    agent_id: str
    user_email: str
    memory_type: str
    content: str
    context: str
    importance: int
    tags: list[str] = []

    @field_validator("memory_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Reject unknown memory types."""
        if v not in VALID_TYPES:
            raise ValueError(f"Invalid memory_type \'{v}\'. Must be one of: {sorted(VALID_TYPES)}")
        return v

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: int) -> int:
        """Clamp importance to 1-10."""
        if not 1 <= v <= 10:
            raise ValueError("importance must be between 1 and 10")
        return v


class SearchRequest(BaseModel):
    """Payload for searching memories."""
    agent_id: str
    user_email: str
    query: str
    max_results: int = 10


class UpdateMemoryRequest(BaseModel):
    """Payload for updating an existing memory."""
    memory_id: str
    user_email: str
    content: Optional[str] = None
    importance: Optional[int] = None

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: Optional[int]) -> Optional[int]:
        """Clamp importance to 1-10 when provided."""
        if v is not None and not 1 <= v <= 10:
            raise ValueError("importance must be between 1 and 10")
        return v


# ── endpoints ──────────────────────────────────────────────────────────────

@router.post("/add")
def add_memory(body: AddMemoryRequest) -> dict:
    """Store a new memory record for an agent."""
    record = {
        "memory_id":    _new_id(),
        "agent_id":     body.agent_id,
        "user_email":   body.user_email,
        "memory_type":  body.memory_type,
        "content":      body.content,
        "context":      body.context,
        "importance":   body.importance,
        "tags":         body.tags,
        "access_count": 0,
        "last_accessed": None,
        "created_at":   datetime.utcnow().isoformat(),
        "deleted":      False,
    }
    _append(record)
    total = sum(
        1 for r in _load_all()
        if r.get("agent_id") == body.agent_id
        and r.get("user_email") == body.user_email
        and not r.get("deleted", False)
    )
    return {"memory_id": record["memory_id"], "message": "Memory saved.", "total_memories": total}


@router.get("/recall/{agent_id}/{user_email}")
def recall_memories(agent_id: str, user_email: str) -> dict:
    """Return all active memories for an agent, sorted by importance then recency."""
    records = [
        r for r in _load_all()
        if r.get("agent_id") == agent_id
        and r.get("user_email") == user_email
        and not r.get("deleted", False)
    ]
    records.sort(key=lambda r: (-r.get("importance", 0), r.get("created_at", "")), reverse=False)
    return {"memories": records, "total": len(records), "agent_id": agent_id}


@router.post("/search")
def search_memories(body: SearchRequest) -> dict:
    """Keyword search across content and tags; increments access_count on hits."""
    query_lower = body.query.lower()
    all_records = _load_all()
    hits: list[dict] = []

    for rec in all_records:
        if rec.get("agent_id") != body.agent_id:
            continue
        if rec.get("user_email") != body.user_email:
            continue
        if rec.get("deleted", False):
            continue
        content_match = query_lower in rec.get("content", "").lower()
        tag_match = any(query_lower in t.lower() for t in rec.get("tags", []))
        context_match = query_lower in rec.get("context", "").lower()
        if content_match or tag_match or context_match:
            rec["access_count"] = rec.get("access_count", 0) + 1
            rec["last_accessed"] = datetime.utcnow().isoformat()
            hits.append(rec)

    hits.sort(key=lambda r: -r.get("importance", 0))
    hits = hits[: body.max_results]
    _save_all(all_records)
    return {"results": hits, "query": body.query, "total_found": len(hits)}


@router.get("/summary/{agent_id}/{user_email}")
def memory_summary(agent_id: str, user_email: str) -> dict:
    """Return aggregated statistics for an agent's memory store."""
    records = [
        r for r in _load_all()
        if r.get("agent_id") == agent_id
        and r.get("user_email") == user_email
        and not r.get("deleted", False)
    ]
    by_type: dict[str, int] = {}
    for r in records:
        mt = r.get("memory_type", "unknown")
        by_type[mt] = by_type.get(mt, 0) + 1

    top = sorted(records, key=lambda r: -r.get("importance", 0))[:5]
    recent = sorted(
        [r for r in records if r.get("last_accessed")],
        key=lambda r: r.get("last_accessed", ""),
        reverse=True,
    )[:5]
    avg_imp = round(sum(r.get("importance", 0) for r in records) / len(records), 2) if records else 0.0

    return {
        "total": len(records),
        "by_type": by_type,
        "top_memories": top,
        "avg_importance": avg_imp,
        "most_recent": recent,
    }


@router.post("/update")
def update_memory(body: UpdateMemoryRequest) -> dict:
    """Update the content or importance of an existing memory."""
    all_records = _load_all()
    updated = False
    for rec in all_records:
        if rec.get("memory_id") == body.memory_id and rec.get("user_email") == body.user_email:
            if not rec.get("deleted", False):
                if body.content is not None:
                    rec["content"] = body.content
                if body.importance is not None:
                    rec["importance"] = body.importance
                updated = True
                break
    if not updated:
        raise HTTPException(status_code=404, detail=f"Memory '{body.memory_id}' not found.")
    _save_all(all_records)
    return {"message": "Memory updated.", "memory_id": body.memory_id}


@router.delete("/delete/{memory_id}/{user_email}")
def delete_memory(memory_id: str, user_email: str) -> dict:
    """Soft-delete a single memory record."""
    all_records = _load_all()
    found = False
    for rec in all_records:
        if rec.get("memory_id") == memory_id and rec.get("user_email") == user_email:
            rec["deleted"] = True
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")
    _save_all(all_records)
    return {"message": f"Memory '{memory_id}' deleted."}


@router.delete("/clear/{agent_id}/{user_email}")
def clear_memories(agent_id: str, user_email: str) -> dict:
    """Soft-delete all memories belonging to an agent."""
    all_records = _load_all()
    count = 0
    for rec in all_records:
        if rec.get("agent_id") == agent_id and rec.get("user_email") == user_email and not rec.get("deleted", False):
            rec["deleted"] = True
            count += 1
    _save_all(all_records)
    return {"message": f"Cleared {count} memories for agent '{agent_id}'.", "cleared_count": count}


@router.get("/types")
def list_memory_types() -> dict:
    """Return all valid memory types with metadata."""
    return {"types": MEMORY_TYPE_DEFS}
