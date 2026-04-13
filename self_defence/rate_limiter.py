"""
rate_limiter.py - Token bucket rate limiter for all AI API calls.
Prevents runaway API costs and protects against abuse.
Implements the Self-Defence capability pillar.
"""
from __future__ import annotations
import os
import time
from collections import defaultdict
from threading import Lock


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.
    Each agent_id gets its own bucket.
    Calls are allowed if the bucket has tokens.
    Tokens refill at the configured rate per minute.
    """

    def __init__(self, calls_per_minute: int = 30) -> None:
        """Initialise the rate limiter with a calls-per-minute limit."""
        self.rate = calls_per_minute / 60.0
        self.capacity = calls_per_minute
        self.buckets: dict = defaultdict(
            lambda: {"tokens": float(calls_per_minute), "last": time.time()}
        )
        self.lock = Lock()

    def is_allowed(self, agent_id: str = "global") -> bool:
        """
        Check if a call from agent_id is allowed right now.
        Returns True if allowed, False if rate limit exceeded.
        """
        with self.lock:
            bucket = self.buckets[agent_id]
            now = time.time()
            elapsed = now - bucket["last"]
            bucket["tokens"] = min(
                self.capacity,
                bucket["tokens"] + elapsed * self.rate
            )
            bucket["last"] = now
            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True
            return False

    def wait_if_needed(
        self, agent_id: str = "global", timeout: float = 5.0
    ) -> bool:
        """
        Wait until a call is allowed or timeout expires.
        Returns True if call is allowed, False if timed out.
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.is_allowed(agent_id):
                return True
            time.sleep(0.1)
        return False

    def get_remaining(self, agent_id: str = "global") -> float:
        """Return the number of remaining tokens for an agent."""
        with self.lock:
            bucket = self.buckets[agent_id]
            now = time.time()
            elapsed = now - bucket["last"]
            tokens = min(
                self.capacity,
                bucket["tokens"] + elapsed * self.rate
            )
            return round(tokens, 2)


rate_limiter = TokenBucketRateLimiter(
    calls_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
)