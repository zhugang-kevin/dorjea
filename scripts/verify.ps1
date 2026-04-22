# verify.ps1 - 元芯智能核心项目日常校验脚本
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot
$errors = 0
Write-Host "元芯智能 - 日常校验" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n[1] 检查关键文件..." -ForegroundColor Yellow
$criticalFiles = @(
    "AGENTS.md", ".cursor\rules\00-global.mdc", ".env", "requirements.txt",
    "agents\meta_agent\models.py", "agents\meta_agent\state.py", "agents\meta_agent\nodes.py",
    "agents\meta_agent\graph.py", "agents\meta_agent\api.py", "agents\meta_agent\registry.py",
    "agents\meta_agent\audit_logger.py", "agents\runtime\ai_clients.py",
    "tools\mcp\filesystem_server\server.py", "tools\mcp\registry_server\server.py",
    "memory\aifactory.db", "memory\schema.sql"
)
foreach ($name in $criticalFiles) {
    $full = Join-Path -Path $RepoRoot -ChildPath $name
    if (Test-Path -LiteralPath $full) { Write-Host "  OK: $name" -ForegroundColor Green }
    else { Write-Host "  MISSING: $name" -ForegroundColor Red; $errors++ }
}
Write-Host "`n[2] 检查源码中的敏感串样例..." -ForegroundColor Yellow
$secretPatterns = @("sk-ant-", "sk-proj-", "ANTHROPIC_API_KEY=sk", "OPENAI_API_KEY=sk")
$secretFound = $false
$scanFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\venv\\' -and $_.FullName -notmatch '\\node_modules\\' -and ($_.Extension -match '\.(py|ps1|md|ts|tsx|js|json|env)$') }
foreach ($pattern in $secretPatterns) {
    foreach ($file in $scanFiles) {
        if ($file.Name -match 'verify|write_verify|fix_') { continue }
        $c = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($null -eq $c) { continue }
        if ($c -match [regex]::Escape($pattern)) {
            Write-Host "  可疑内容: $($file.FullName)" -ForegroundColor Red
            $errors++
            $secretFound = $true
        }
    }
}
if (-not $secretFound) { Write-Host "  OK: 未发现常见境外密钥样例" -ForegroundColor Green }
Write-Host "`n[3] 检查 Python 导入..." -ForegroundColor Yellow
$imports = @(
    "from agents.meta_agent.models import TaskSpec, AgentSpec, FounderReport",
    "from agents.meta_agent.state import MetaAgentState",
    "from agents.meta_agent.nodes import parse_request, return_report",
    "from agents.meta_agent.graph import meta_agent_graph",
    "from agents.meta_agent.api import app",
    "from agents.runtime.ai_clients import PrimaryChatClient, AIChatRequest"
)
foreach ($import in $imports) {
    $result = python -c "$import; print('OK')" 2>&1
    if ($result -match "OK") { Write-Host "  OK: $import" -ForegroundColor Green }
    else { Write-Host "  FAILED: $import" -ForegroundColor Red; $errors++ }
}
Write-Host "`n[4] 检查数据库..." -ForegroundColor Yellow
$dbScript = Join-Path -Path $RepoRoot -ChildPath "memory\check_db_verify.py"
$dbResult = python $dbScript 2>&1
if ($dbResult -match "^OK:") {
    Write-Host "  OK: 数据库可访问。表: $($dbResult -replace '^OK:','')" -ForegroundColor Green
} else {
    Write-Host "  FAILED: $dbResult" -ForegroundColor Red
    $errors++
}
Write-Host "`n[5] 检查代码中的 TODO 注释..." -ForegroundColor Yellow
$pyFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -Filter "*.py" |
    Where-Object { $_.FullName -notmatch '\\venv\\' }
$todoFound = $false
foreach ($file in $pyFiles) {
    $lines = Get-Content -LiteralPath $file.FullName
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*#.*(TODO|FIXME)") {
            Write-Host "  TODO: $($file.Name) 行 $($i+1)" -ForegroundColor Red
            $errors++
            $todoFound = $true
        }
    }
}
if (-not $todoFound) { Write-Host "  OK: 未发现 TODO/FIXME 注释" -ForegroundColor Green }
Write-Host "`n========================================" -ForegroundColor Cyan
if ($errors -eq 0) { Write-Host "校验通过 - 0 个错误" -ForegroundColor Green }
else { Write-Host "校验失败 - 共 $errors 个问题" -ForegroundColor Red }
Write-Host "========================================" -ForegroundColor Cyan
