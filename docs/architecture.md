# Architecture — Dorjea AI Factory

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