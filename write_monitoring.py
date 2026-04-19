import os

CONTENT = '''\
from __future__ import annotations
import json
import os
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/monitor", tags=["Real-Time Monitoring"])

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MONITOR_FILE = os.path.join(_BASE, "memory", "agent_monitor.jsonl")

VALID_EVENT_TYPES = {
    "task_started", "task_progress", "task_completed", "task_failed",
    "token_consumed", "gate_check", "memory_saved", "tool_used",
}


# ── helpers ────────────────────────────────────────────────────────────────

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _read_all() -> list[dict]:
    if not os.path.exists(MONITOR_FILE):
        return []
    records: list[dict] = []
    with open(MONITOR_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def load_events(agent_id: str, user_email: str) -> list[dict]:
    """Load all non-deleted events for a specific agent and user."""
    return [
        r for r in _read_all()
        if r.get("agent_id") == agent_id
        and r.get("user_email", "").lower() == user_email.lower()
        and not r.get("deleted", False)
    ]


def save_event(event_data: dict) -> str:
    """Append event to MONITOR_FILE and return its event_id."""
    _ensure_dir(MONITOR_FILE)
    with open(MONITOR_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_data) + "\\n")
    return event_data["event_id"]


# ── request models ─────────────────────────────────────────────────────────

class MonitorEventRequest(BaseModel):
    agent_id: str
    user_email: str
    event_type: str
    message: str
    data: dict = {}
    tokens_used: int = 0


# ── endpoints ──────────────────────────────────────────────────────────────

@router.get("/stream/{agent_id}/{user_email}")
async def stream_events(agent_id: str, user_email: str):
    """SSE endpoint — streams real-time monitoring events for an agent."""

    async def event_generator():
        last_count = 0
        idle_seconds = 0
        while idle_seconds < 300:
            events = load_events(agent_id, user_email)
            if len(events) > last_count:
                for event in events[last_count:]:
                    yield "data: " + json.dumps(event) + "\\n\\n"
                last_count = len(events)
                idle_seconds = 0
            else:
                idle_seconds += 2
                ping = {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                yield "data: " + json.dumps(ping) + "\\n\\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/event")
def post_event(body: MonitorEventRequest) -> dict:
    """Save a monitoring event and return its event_id."""
    event_type = body.event_type if body.event_type in VALID_EVENT_TYPES else "task_progress"
    event = {
        "event_id": "evt_" + secrets.token_hex(8),
        "agent_id": body.agent_id,
        "user_email": body.user_email,
        "event_type": event_type,
        "message": body.message,
        "data": body.data,
        "tokens_used": body.tokens_used,
        "timestamp": datetime.utcnow().isoformat(),
        "deleted": False,
    }
    event_id = save_event(event)
    return {"event_id": event_id, "saved": True}


@router.get("/history/{agent_id}/{user_email}")
def get_history(agent_id: str, user_email: str) -> dict:
    """Return the last 50 monitoring events for an agent."""
    events = load_events(agent_id, user_email)
    return {
        "events": events[-50:],
        "total": len(events),
        "agent_id": agent_id,
    }


@router.get("/active/{user_email}")
def get_active_agents(user_email: str) -> dict:
    """Return agents with monitoring events in the last 30 minutes."""
    cutoff = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
    all_events = [
        r for r in _read_all()
        if r.get("user_email", "").lower() == user_email.lower()
        and not r.get("deleted", False)
        and r.get("timestamp", "") >= cutoff
    ]
    by_agent: dict[str, dict] = {}
    for ev in all_events:
        aid = ev["agent_id"]
        if aid not in by_agent:
            by_agent[aid] = {"agent_id": aid, "last_event": ev["timestamp"], "event_count": 0}
        by_agent[aid]["event_count"] += 1
        if ev["timestamp"] > by_agent[aid]["last_event"]:
            by_agent[aid]["last_event"] = ev["timestamp"]
    return {"active_agents": sorted(by_agent.values(), key=lambda x: x["last_event"], reverse=True)}


@router.delete("/clear/{agent_id}/{user_email}")
def clear_events(agent_id: str, user_email: str) -> dict:
    """Soft-delete all monitoring events for an agent."""
    records = _read_all()
    cleared = 0
    for r in records:
        if (
            r.get("agent_id") == agent_id
            and r.get("user_email", "").lower() == user_email.lower()
            and not r.get("deleted", False)
        ):
            r["deleted"] = True
            cleared += 1
    _ensure_dir(MONITOR_FILE)
    with open(MONITOR_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\\n")
    return {"message": f"Cleared {cleared} event(s) for agent '{agent_id}'.", "cleared": cleared}


@router.get("/stats/{user_email}")
def get_stats(user_email: str) -> dict:
    """Return monitoring statistics for a user today."""
    today = datetime.utcnow().date().isoformat()
    all_events = [
        r for r in _read_all()
        if r.get("user_email", "").lower() == user_email.lower()
        and not r.get("deleted", False)
        and r.get("timestamp", "")[:10] == today
    ]
    total_tokens = sum(r.get("tokens_used", 0) for r in all_events)
    by_type: dict[str, int] = {}
    by_agent: dict[str, int] = {}
    for ev in all_events:
        et = ev.get("event_type", "unknown")
        by_type[et] = by_type.get(et, 0) + 1
        aid = ev.get("agent_id", "unknown")
        by_agent[aid] = by_agent.get(aid, 0) + 1
    most_active = max(by_agent, key=lambda k: by_agent[k]) if by_agent else None
    return {
        "stats": {
            "total_events_today": len(all_events),
            "most_active_agent": most_active,
            "total_tokens_monitored_today": total_tokens,
            "events_by_type": by_type,
        }
    }
'''

dest = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agents", "meta_agent", "monitoring.py"
)
with open(dest, "w", encoding="utf-8") as f:
    f.write(CONTENT)
print(f"Written {len(CONTENT)} chars to {dest}")
