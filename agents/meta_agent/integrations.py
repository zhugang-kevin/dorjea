"""
Real integrations: email (Resend with retry), database connector, webhook retry.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@yuancore.ai")
RESEND_BASE = "https://api.resend.com"
_EMAIL_MAX_RETRIES = 3
_EMAIL_RETRY_DELAY = 2.0


# ---------------------------------------------------------------------------
# Email integration (Resend) with retry
# ---------------------------------------------------------------------------

def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    text: str | None = None,
) -> tuple[bool, str]:
    """
    Send email via Resend API with exponential-backoff retry.
    Returns (success, message_or_error).
    """
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set, skipping email to %s", to)
        return True, "skipped (no API key)"

    recipients = [to] if isinstance(to, str) else to
    payload: dict[str, Any] = {
        "from": EMAIL_FROM,
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    last_error = ""
    for attempt in range(1, _EMAIL_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{RESEND_BASE}/emails",
                    headers={
                        "Authorization": f"Bearer {RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(payload),
                )
            if resp.status_code in (200, 201):
                return True, resp.json().get("id", "sent")
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning("Email attempt %d/%d failed: %s", attempt, _EMAIL_MAX_RETRIES, last_error)
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Email attempt %d/%d exception: %s", attempt, _EMAIL_MAX_RETRIES, exc)

        if attempt < _EMAIL_MAX_RETRIES:
            time.sleep(_EMAIL_RETRY_DELAY * attempt)

    return False, last_error


def send_email_async(to: str, subject: str, html: str, text: str | None = None) -> None:
    """Fire-and-forget email in a background thread."""
    import threading
    threading.Thread(
        target=send_email,
        args=(to, subject, html, text),
        daemon=True,
    ).start()


# ---------------------------------------------------------------------------
# Database connector abstraction
# ---------------------------------------------------------------------------

class DatabaseConnector:
    """
    Thin abstraction over SQLite (dev) / PostgreSQL (prod).
    Reads DATABASE_URL from env; falls back to SQLite.
    """

    def __init__(self) -> None:
        self._url = os.getenv("DATABASE_URL", "sqlite:///memory/agentcore.db")
        self._engine = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from sqlalchemy import create_engine
            self._engine = create_engine(self._url, pool_pre_ping=True)
        except Exception as exc:
            logger.error("DB engine creation failed: %s", exc)
            raise
        return self._engine

    def execute(self, sql: str, params: dict | None = None) -> list[dict]:
        from sqlalchemy import text
        engine = self._get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            if result.returns_rows:
                cols = list(result.keys())
                return [dict(zip(cols, row)) for row in result.fetchall()]
            conn.commit()
            return []

    def health(self) -> bool:
        try:
            self.execute("SELECT 1")
            return True
        except Exception:
            return False


db = DatabaseConnector()


# ---------------------------------------------------------------------------
# Webhook retry queue
# ---------------------------------------------------------------------------

import threading
from collections import deque
from dataclasses import dataclass, field

@dataclass
class WebhookJob:
    url: str
    payload: dict
    headers: dict = field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 5
    next_attempt_at: float = field(default_factory=time.time)


class WebhookRetryQueue:
    """
    Background queue that retries failed outbound webhooks with backoff.
    """

    def __init__(self) -> None:
        self._queue: deque[WebhookJob] = deque()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def enqueue(self, url: str, payload: dict, headers: dict | None = None) -> None:
        job = WebhookJob(url=url, payload=payload, headers=headers or {})
        with self._lock:
            self._queue.append(job)

    def _worker(self) -> None:
        while True:
            time.sleep(5)
            now = time.time()
            with self._lock:
                pending = [j for j in self._queue if j.next_attempt_at <= now]
                for job in pending:
                    self._queue.remove(job)

            for job in pending:
                self._dispatch(job)

    def _dispatch(self, job: WebhookJob) -> None:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(job.url, json=job.payload, headers=job.headers)
            if resp.status_code < 300:
                logger.info("Webhook delivered to %s", job.url)
                return
            logger.warning("Webhook %s returned %d", job.url, resp.status_code)
        except Exception as exc:
            logger.warning("Webhook %s failed: %s", job.url, exc)

        job.attempts += 1
        if job.attempts < job.max_attempts:
            job.next_attempt_at = time.time() + (2 ** job.attempts) * 10
            with self._lock:
                self._queue.append(job)
        else:
            logger.error("Webhook %s exhausted after %d attempts", job.url, job.max_attempts)


webhook_queue = WebhookRetryQueue()
