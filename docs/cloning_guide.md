# Cloning Guide — Create a New Meta-Agent

## What You Are Doing
Creating a second Meta-Agent that specialises in one department only.

## Steps
1. Copy the entire E:\Dorjea folder to a new location
   Example: E:\Dorjea_Marketing

2. Open the new folder in PowerShell:
   Set-Location E:\Dorjea_Marketing

3. Open agents\meta_agent\policy.yaml and change:
   meta_agent_name: meta-agent-marketing
   specialization: marketing
   allowed_departments: [marketing, sales]

4. Initialize the new database:
   python memory\init_db.py

5. Run verification:
   .\scripts\verify.ps1

## What Never Changes in a Clone
- Python code in agents\meta_agent\
- MCP servers in tools\mcp\
- JSON schemas in tools\schemas\
- Governance files AGENTS.md and CLAUDE.md
- The audit log format

## Clone Ideas
- Dorjea_Marketing — marketing and sales agents only
- Dorjea_Finance — finance and compliance agents only
- Dorjea_Engineering — coding and DevOps agents only
- Dorjea_Research — research and data analysis only