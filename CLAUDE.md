# CLAUDE.md — Dorjea AI Factory Project Memory

## ENVIRONMENT
- OS: Windows 11
- Shell: PowerShell 7 ONLY. Never write bash. Never use Linux commands. Never use forward slashes in paths.
- Root folder: E:\Dorjea
- GitHub remote: https://github.com/zhugang-kevin/dorjea
- Python: 3.11.9 (venv at E:\Dorjea\venv)
- Editor: Cursor + Claude Code

## FROZEN PORT MAP
- FastAPI backend: 8000
- Filesystem MCP server: 8001
- Registry MCP server: 8002
- GitHub MCP server: 8003
- PostgreSQL: 5432

## FROZEN TECH STACK
- LangGraph 1.1.x (StateGraph API only)
- FastMCP 3.x
- FastAPI 0.115+
- Pydantic v2 (@field_validator only, never @validator)
- anthropic SDK (latest installed)
- openai SDK (latest installed)
- SQLite for dev, PostgreSQL 16 for prod
- pgvector for vector search (NOT qdrant)

## FROZEN MODELS
- Primary builder: claude-sonnet-4-6 (read from .env as PRIMARY_MODEL)
- Verifier: gpt-4o (read from .env as VERIFIER_MODEL)
- Heavy decisions only: claude-opus-4-6 (read from .env as HEAVY_MODEL)
- All model names must be read from .env — never hardcoded

## WORKFLOW — 9 NODES EXACTLY IN THIS ORDER
1. parse_request
2. validate_spec
3. check_registry
4. generate_spec
5. verify_spec
6. generate_code
7. run_tests
8. register_agent
9. return_report

## MCP SERVERS — PHASE 1 ONLY
- tools\mcp\filesystem_server\server.py (port 8001)
- tools\mcp\registry_server\server.py (port 8002)
- tools\mcp\github_server\server.py (port 8003)
- Monitor and defence servers are Phase 2 — do not create them

## CODING STANDARDS — NON-NEGOTIABLE
- All inputs and outputs: Pydantic v2 models. No raw dicts ever.
- All secrets: os.getenv() only. Never hardcode.
- All API calls: wrapped in try/except with human-readable error messages.
- All functions: must have a docstring.
- All functions: max 50 lines.
- All paths: use os.path.join() or pathlib.Path — never hardcoded backslashes.
- Never use Redis or Celery — LangGraph state handles all messaging.
- Never create top-level folders not in the frozen structure.
- Never leave TODO or placeholder comments in any file.
- Never use @validator — always use @field_validator (Pydantic v2).

## OUTPUT RULES
- Never provide code snippets — always rewrite the complete file.
- Every response that touches a file must end with a PowerShell VERIFY command.
- Never use bash syntax. PowerShell only.

## CRASH PROTOCOL
If the founder types CRASH:
1. Stop all generation immediately.
2. Re-read the last 5 messages.
3. Identify what went wrong in plain English.
4. Wait for the founder to say continue before doing anything.

## TOKEN BUDGET
- Max 20,000 tokens per task.
- If approaching limit: stop, report remaining work, wait for approval.

## START COMMANDS
Start API server:
Set-Location E:\Dorjea
.\venv\Scripts\Activate.ps1
uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port 8000

Start Filesystem MCP:
python tools\mcp\filesystem_server\server.py

Start Registry MCP:
python tools\mcp\registry_server\server.py

## SAFETY RULES
- Infinite loop protection: max 3 retries per node, then halt and report.
- Token spike protection: hard ceiling 20,000 tokens per task.
- Forbidden action: halt immediately, log, notify founder.
- Tool crash: save checkpoint, report, wait for founder.
