-- Dorjea AI Factory — Database Schema
-- SQLite for development, PostgreSQL for production

-- Agents Registry
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL DEFAULT '1.0',
    mission TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','idle','frozen','requires_review','archived')),
    default_model TEXT NOT NULL,
    fallback_model TEXT,
    allowed_tools TEXT NOT NULL,
    token_budget INTEGER NOT NULL DEFAULT 20000,
    spec_yaml TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'meta-agent'
);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','escalated')),
    input_json TEXT NOT NULL,
    output_json TEXT,
    tokens_used INTEGER DEFAULT 0,
    tokens_budget INTEGER NOT NULL DEFAULT 20000,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Audit Log (append-only)
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    task_id TEXT,
    action TEXT NOT NULL,
    details_json TEXT,
    tokens_used INTEGER DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 1,
    logged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Token Budget Tracker
CREATE TABLE IF NOT EXISTS token_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    task_id TEXT,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    budget INTEGER NOT NULL DEFAULT 20000,
    budget_used_pct REAL NOT NULL DEFAULT 0.0,
    logged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
