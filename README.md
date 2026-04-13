# Dorjea AI Factory

An AI-powered company operating system for solo founders.
Built on Windows 11, PowerShell 7, Claude 4.6, LangGraph 1.1, FastMCP 3.x, FastAPI.

## Quick Start
1. Set-Location E:\Dorjea
2. .\venv\Scripts\Activate.ps1
3. . .\scripts\clear_proxy.ps1
4. uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port 8000
5. Open http://127.0.0.1:8000/docs

## Create Your First Agent
POST http://127.0.0.1:8000/agents/create
Body: {"request": "Create a content writing agent for our marketing team."}

## Key Endpoints
- POST /agents/create
- GET /agents
- GET /health
- GET /metrics
- GET /audit

## Daily Commands
Start server: uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port 8000
Run tests: pytest agents\meta_agent\tests\test_core.py -v
Verify: .\scripts\verify.ps1
