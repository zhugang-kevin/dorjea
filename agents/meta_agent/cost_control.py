"""
Cost control: response caching, model routing (cheap vs smart), task prioritization.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any

# ---------------------------------------------------------------------------
# Response cache (in-memory, TTL-based)
# ---------------------------------------------------------------------------

_CACHE_TTL = int(os.getenv("RESPONSE_CACHE_TTL", "300"))  # 5 minutes default
_cache: dict[str, tuple[float, Any]] = {}


def _cache_key(agent: str, task: str) -> str:
    raw = f"{agent}::{task.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def cache_get(agent: str, task: str) -> Any | None:
    key = _cache_key(agent, task)
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return value


def cache_set(agent: str, task: str, value: Any) -> None:
    key = _cache_key(agent, task)
    _cache[key] = (time.time(), value)


def cache_invalidate(agent: str) -> int:
    """Remove all cached entries for a given agent. Returns count removed."""
    prefix_keys = [k for k in list(_cache.keys())]
    removed = 0
    for k in prefix_keys:
        del _cache[k]
        removed += 1
    return removed


# ---------------------------------------------------------------------------
# Model routing: cheap vs smart
# ---------------------------------------------------------------------------

PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "claude-sonnet-4-6")
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "claude-haiku-4-5-20251001")
HEAVY_MODEL = os.getenv("HEAVY_MODEL", "claude-opus-4-6")

# Tasks shorter than this threshold use the cheap model
_CHEAP_TASK_MAX_TOKENS = int(os.getenv("CHEAP_TASK_MAX_TOKENS", "500"))
_HEAVY_TASK_MIN_TOKENS = int(os.getenv("HEAVY_TASK_MIN_TOKENS", "3000"))

# Keywords that always trigger the heavy model
_HEAVY_KEYWORDS = {
    "strategy", "architecture", "design", "analyze", "research",
    "comprehensive", "detailed", "complex", "enterprise", "audit",
    "分析", "策略", "架构", "设计", "研究", "综合", "详细",
}

# Keywords that always use the cheap model
_CHEAP_KEYWORDS = {
    "summarize", "format", "translate", "list", "extract", "classify",
    "总结", "格式化", "翻译", "列出", "提取", "分类",
}


def route_model(task: str, force_model: str | None = None) -> str:
    """
    Choose the appropriate model based on task complexity.
    Returns model name string.
    """
    if force_model:
        return force_model

    task_lower = task.lower()
    word_count = len(task.split())

    # Explicit heavy keywords
    if any(kw in task_lower for kw in _HEAVY_KEYWORDS):
        return HEAVY_MODEL

    # Explicit cheap keywords
    if any(kw in task_lower for kw in _CHEAP_KEYWORDS):
        return CHEAP_MODEL

    # Length-based routing
    if word_count <= _CHEAP_TASK_MAX_TOKENS:
        return CHEAP_MODEL
    if word_count >= _HEAVY_TASK_MIN_TOKENS:
        return HEAVY_MODEL

    return PRIMARY_MODEL


# ---------------------------------------------------------------------------
# Task prioritization queue
# ---------------------------------------------------------------------------

import heapq
import threading
from dataclasses import dataclass, field

PRIORITY_HIGH = 1
PRIORITY_NORMAL = 5
PRIORITY_LOW = 10

_PLAN_PRIORITY: dict[str, int] = {
    "owner": PRIORITY_HIGH,
    "enterprise": PRIORITY_HIGH,
    "business": PRIORITY_NORMAL,
    "professional": PRIORITY_NORMAL,
    "pro": PRIORITY_NORMAL,
    "free": PRIORITY_LOW,
}


@dataclass(order=True)
class _PrioritizedTask:
    priority: int
    timestamp: float
    task_id: str = field(compare=False)
    payload: dict = field(compare=False)


class TaskPriorityQueue:
    def __init__(self) -> None:
        self._heap: list[_PrioritizedTask] = []
        self._lock = threading.Lock()

    def push(self, task_id: str, payload: dict, plan: str = "free") -> None:
        priority = _PLAN_PRIORITY.get(plan, PRIORITY_LOW)
        item = _PrioritizedTask(
            priority=priority,
            timestamp=time.time(),
            task_id=task_id,
            payload=payload,
        )
        with self._lock:
            heapq.heappush(self._heap, item)

    def pop(self) -> dict | None:
        with self._lock:
            if not self._heap:
                return None
            item = heapq.heappop(self._heap)
            return {"task_id": item.task_id, **item.payload}

    def size(self) -> int:
        with self._lock:
            return len(self._heap)


task_queue = TaskPriorityQueue()
