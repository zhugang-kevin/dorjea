# verify.ps1 - Daily verification script for Dorjea AI Factory
Set-Location "E:\Dorjea\Dorjea"
$errors = 0
Write-Host "Dorjea AI Factory - Daily Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n[1] Checking critical files..." -ForegroundColor Yellow
$criticalFiles = @(
    "CLAUDE.md","AGENTS.md",".cursor\rules\00-global.mdc",".env","requirements.txt",
    "agents\meta_agent\models.py","agents\meta_agent\state.py","agents\meta_agent\nodes.py",
    "agents\meta_agent\graph.py","agents\meta_agent\api.py","agents\meta_agent\registry.py",
    "agents\meta_agent\audit_logger.py","agents\runtime\ai_clients.py",
    "tools\mcp\filesystem_server\server.py","tools\mcp\registry_server\server.py",
    "tools\mcp\github_server\server.py","memory\aifactory.db","memory\schema.sql"
)
foreach ($file in $criticalFiles) {
    if (Test-Path $file) { Write-Host "  OK: $file" -ForegroundColor Green }
    else { Write-Host "  MISSING: $file" -ForegroundColor Red; $errors++ }
}
Write-Host "`n[2] Checking for exposed secrets..." -ForegroundColor Yellow
$secretPatterns = @("sk-ant-","sk-proj-","ANTHROPIC_API_KEY=sk","OPENAI_API_KEY=sk")
$committedFiles = git ls-files 2>$null
$secretFound = $false
foreach ($pattern in $secretPatterns) {
    $hits = $committedFiles | Where-Object { $_ -notmatch "verify|write_verify|fix_" } | ForEach-Object {
        if (Test-Path $_) {
            $c = Get-Content $_ -Raw -ErrorAction SilentlyContinue
            if ($c -match [regex]::Escape($pattern)) { $_ }
        }
    }
    if ($hits) { Write-Host "  SECRET EXPOSED in: $hits" -ForegroundColor Red; $errors++; $secretFound = $true }
}
if (-not $secretFound) { Write-Host "  OK: No secrets found in committed files" -ForegroundColor Green }
Write-Host "`n[3] Checking Python imports..." -ForegroundColor Yellow
$imports = @(
    "from agents.meta_agent.models import TaskSpec, AgentSpec, FounderReport",
    "from agents.meta_agent.state import MetaAgentState",
    "from agents.meta_agent.nodes import parse_request, return_report",
    "from agents.meta_agent.graph import meta_agent_graph",
    "from agents.meta_agent.api import app",
    "from agents.runtime.ai_clients import ClaudeClient, OpenAIClient"
)
foreach ($import in $imports) {
    $result = python -c "$import; print('OK')" 2>&1
    if ($result -match "OK") { Write-Host "  OK: $import" -ForegroundColor Green }
    else { Write-Host "  FAILED: $import" -ForegroundColor Red; $errors++ }
}
Write-Host "`n[4] Checking database..." -ForegroundColor Yellow
$dbResult = python memory\check_db_verify.py 2>&1
if ($dbResult -match "^OK:") { Write-Host "  OK: Database reachable. Tables: $($dbResult -replace '^OK:','')" -ForegroundColor Green }
else { Write-Host "  FAILED: $dbResult" -ForegroundColor Red; $errors++ }
Write-Host "`n[5] Checking for TODO comments in code..." -ForegroundColor Yellow
$pyFiles = Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.FullName -notmatch "venv" }
$todoFound = $false
foreach ($file in $pyFiles) {
    $lines = Get-Content $file.FullName
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*#.*(TODO|FIXME)") {
            Write-Host "  TODO found: $($file.Name) line $($i+1)" -ForegroundColor Red
            $errors++; $todoFound = $true
        }
    }
}
if (-not $todoFound) { Write-Host "  OK: No TODO comments found in code" -ForegroundColor Green }
Write-Host "`n========================================" -ForegroundColor Cyan
if ($errors -eq 0) { Write-Host "VERIFICATION PASSED - 0 errors" -ForegroundColor Green }
else { Write-Host "VERIFICATION FAILED - $errors error(s) found" -ForegroundColor Red }
Write-Host "========================================" -ForegroundColor Cyan
