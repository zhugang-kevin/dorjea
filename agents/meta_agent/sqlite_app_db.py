"""
可选的本地 SQLite 结构初始化。

与现有基于 JSONL 的用户与业务数据并存，便于后续逐步迁移；
启动时调用不会覆盖已有 JSONL 数据。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("SQLITE_PATH", "./data/agentcore.db"))


def init_sqlite_schema() -> None:
    """创建 AgentCore 可选 SQLite 表（若不存在）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                plan TEXT DEFAULT 'free',
                is_admin INTEGER DEFAULT 0,
                tokens_used_today INTEGER DEFAULT 0,
                last_token_reset TEXT,
                wechat_openid TEXT,
                phone TEXT,
                referral_code TEXT UNIQUE,
                referred_by TEXT,
                discount_percent INTEGER DEFAULT 100,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                token_budget INTEGER DEFAULT 10000,
                tasks_completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                task_description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                tokens_used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_orders (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                plan TEXT NOT NULL,
                amount_cny INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                trade_no TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                config TEXT,
                status TEXT DEFAULT 'inactive',
                run_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_run_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                agent_id TEXT,
                filename TEXT NOT NULL,
                content TEXT,
                size_kb INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
