arch = """# Architecture — Dorjea AI Factory

## System Overview
The Dorjea AI Factory is a self-governing AI company operating system.
The Meta-Agent sits at the top and creates all other agents automatically.

## Technology Stack
| Layer | Technology |
|---|---|
| Orchestration | LangGraph 1.1.x |
| Primary AI | Claude Sonnet 4.6 |
| Verifier AI | GPT-4o (Phase 2) |
| API | FastAPI 0.115 |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| MCP Tools | FastMCP 3.x |
| Models | Pydantic v2 |

## Layer Architecture
1. Governance Layer — AGENTS.md, CLAUDE.md, policy.yaml
2. Orchestration Layer — LangGraph 9-node workflow
3. Agent Management Layer — Registry + Meta-Agent
4. Cognitive Layer — Claude Sonnet 4.6
5. Tool Layer — 3 MCP servers
6. Data Layer — SQLite / PostgreSQL
7. Observability Layer — Audit logs + health monitor

## LangGraph Workflow — 9 Nodes
parse_request -> validate_spec -> check_registry -> generate_spec
-> verify_spec -> generate_code -> run_tests -> register_agent -> return_report

## Self-* Capabilities
- Self-Defence: injection_detector.py + rate_limiter.py
- Self-Governance: policy_engine.py
- Self-Correction: quality_scorer.py
- Self-Token: budget_manager.py
- Self-Monitoring: health_monitor.py
- Self-SEO: seo_generator.py
- Self-AIEO: aieo_generator.py

## Port Map
- FastAPI: 8000
- Filesystem MCP: 8001
- Registry MCP: 8002
- GitHub MCP: 8003
- PostgreSQL: 5432

## Key Files
- agents/meta_agent/nodes.py — all 9 node functions
- agents/meta_agent/graph.py — LangGraph wiring
- agents/meta_agent/api.py — FastAPI endpoints
- agents/meta_agent/registry.py — database operations
- agents/runtime/ai_clients.py — Claude and OpenAI wrappers
"""

token = """# Token Budget — Dorjea AI Factory

## Per-Task Budget
Maximum tokens per agent creation: 20,000
Daily total budget: 100,000

## Cost Estimates (Claude Sonnet 4.6)
| Node | Estimated Tokens |
|---|---|
| parse_request | 500-1,000 |
| validate_spec | 100-200 |
| check_registry | 50-100 |
| generate_spec | 2,000-4,000 |
| verify_spec | 1,500-3,000 |
| generate_code | 3,000-6,000 |
| run_tests | 200-500 |
| register_agent | 50-100 |
| return_report | 100-200 |
| TOTAL | 7,500-15,100 |

## Cost Per Agent Creation
Estimated: USD 0.15 - 0.35 per agent

## Monitoring
- Metrics log: logs/metrics.jsonl
- Health endpoint: GET /health
- Metrics endpoint: GET /metrics

## Rules
- Hard ceiling: 20,000 tokens per task
- If exceeded: halt, save checkpoint, request approval
- Daily budget: 100,000 tokens
- If exceeded: API returns 429 until next day
"""

clone = """# Cloning Guide — Create a New Meta-Agent

## What You Are Doing
Creating a second Meta-Agent that specialises in one department only.

## Steps
1. Copy the entire E:\\Dorjea folder to a new location
   Example: E:\\Dorjea_Marketing

2. Open the new folder in PowerShell:
   Set-Location E:\\Dorjea_Marketing

3. Open agents\\meta_agent\\policy.yaml and change:
   meta_agent_name: meta-agent-marketing
   specialization: marketing
   allowed_departments: [marketing, sales]

4. Initialize the new database:
   python memory\\init_db.py

5. Run verification:
   .\\scripts\\verify.ps1

## What Never Changes in a Clone
- Python code in agents\\meta_agent\\
- MCP servers in tools\\mcp\\
- JSON schemas in tools\\schemas\\
- Governance files AGENTS.md and CLAUDE.md
- The audit log format

## Clone Ideas
- Dorjea_Marketing — marketing and sales agents only
- Dorjea_Finance — finance and compliance agents only
- Dorjea_Engineering — coding and DevOps agents only
- Dorjea_Research — research and data analysis only
"""

with open("docs/architecture.md", "w", encoding="utf-8") as f:
    f.write(arch.strip())

with open("docs/token_budget.md", "w", encoding="utf-8") as f:
    f.write(token.strip())

with open("docs/cloning_guide.md", "w", encoding="utf-8") as f:
    f.write(clone.strip())

print("All 3 documentation files created")
