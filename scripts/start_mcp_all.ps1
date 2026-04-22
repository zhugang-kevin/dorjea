#Requires -Version 5.1
# ========================================
# 元芯智能 — MCP 服务器启动（独立进程，避免 Start-Job 缓冲区挂起）
# ========================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "[元芯智能] 未找到 Python 虚拟环境: $PythonExe" -ForegroundColor Red
    exit 1
}

foreach ($k in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
    Set-Item -Path "Env:$k" -Value "" -ErrorAction SilentlyContinue
}

$env:PYTHONPATH = $RepoRoot
$env:AI_FACTORY_ROOT = $RepoRoot

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  元芯智能 MCP 服务器启动（修复版）" -ForegroundColor Cyan
Write-Host "  仓库: $RepoRoot" -ForegroundColor Gray
Write-Host "================================================" -ForegroundColor Cyan

function Kill-Port {
    param([int]$Port)
    $connections = netstat -ano 2>$null | Select-String ":$Port\s"
    if (-not $connections) { return }
    $procIds = $connections | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
    foreach ($procId in $procIds) {
        if ($procId -match '^\d+$' -and $procId -ne '0') {
            try { Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
    Start-Sleep -Milliseconds 500
}

function Start-McpProcess {
    param(
        [string]$DisplayName,
        [string]$ScriptRelative,
        [hashtable]$ExtraEnv = @{}
    )

    $scriptPath = Join-Path $RepoRoot $ScriptRelative
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        Write-Host "  [跳过] $DisplayName — 未找到: $scriptPath" -ForegroundColor Yellow
        return $null
    }

    $rootEsc = $RepoRoot -replace "'", "''"
    $pyEsc = $PythonExe -replace "'", "''"
    $scrEsc = $scriptPath -replace "'", "''"

    $envLines = @(
        "`$env:PYTHONPATH='$rootEsc'",
        "`$env:AI_FACTORY_ROOT='$rootEsc'"
    )
    foreach ($key in $ExtraEnv.Keys) {
        $val = "$($ExtraEnv[$key])" -replace "'", "''"
        $envLines += "`$env:$key='$val'"
    }
    $envBlock = $envLines -join "; "

    $cmd = "$envBlock; Set-Location -LiteralPath '$rootEsc'; & '$pyEsc' '$scrEsc'"

    $proc = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", $cmd
    ) -PassThru -WindowStyle Minimized

    Write-Host "  [已启动] $DisplayName  PID=$($proc.Id)" -ForegroundColor Green
    return $proc
}

Write-Host "清理占用端口..." -ForegroundColor Yellow
foreach ($p in @(8001, 8002, 8003, 8004, 8005)) { Kill-Port $p }

$pids = @()

$pr = Start-McpProcess -DisplayName "Filesystem MCP (8001)" -ScriptRelative "tools\mcp\filesystem_server\server.py" -ExtraEnv @{ FILESYSTEM_MCP_PORT = "8001" }
if ($pr) { $pids += $pr.Id }
Start-Sleep -Seconds 1

$pr = Start-McpProcess -DisplayName "Registry MCP (8002)" -ScriptRelative "tools\mcp\registry_server\server.py" -ExtraEnv @{ REGISTRY_MCP_PORT = "8002" }
if ($pr) { $pids += $pr.Id }
Start-Sleep -Seconds 1

$pr = Start-McpProcess -DisplayName "GitHub/Git MCP (8003)" -ScriptRelative "tools\mcp\github_server\server.py" -ExtraEnv @{ GITHUB_MCP_PORT = "8003" }
if ($pr) { $pids += $pr.Id }
Start-Sleep -Seconds 1

$pr = Start-McpProcess -DisplayName "Monitor MCP (8004)" -ScriptRelative "tools\mcp\monitor_server\server.py"
if ($pr) { $pids += $pr.Id }
Start-Sleep -Seconds 1

$pr = Start-McpProcess -DisplayName "Defence MCP (8005)" -ScriptRelative "tools\mcp\defence_server\server.py"
if ($pr) { $pids += $pr.Id }

if ($pids.Count -gt 0) {
    ($pids -join ",") | Out-File -FilePath (Join-Path $RepoRoot "mcp_pids.txt") -Encoding UTF8
    Write-Host "PID 已保存到: $(Join-Path $RepoRoot 'mcp_pids.txt')" -ForegroundColor Gray
}

Write-Host "`n验证 MCP 服务（根路径探测）..." -ForegroundColor Yellow
$services = @(
    @{ Name = "Filesystem"; Url = "http://127.0.0.1:8001" },
    @{ Name = "Registry";   Url = "http://127.0.0.1:8002" }
)
foreach ($svc in $services) {
    try {
        $null = Invoke-WebRequest -Uri $svc.Url -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-Host "  OK $($svc.Name): $($svc.Url)" -ForegroundColor Green
    } catch {
        Write-Host "  启动中或未响应根路径: $($svc.Name)" -ForegroundColor Yellow
    }
}

Write-Host "`n本地端点（默认）：" -ForegroundColor White
Write-Host "  Filesystem  http://127.0.0.1:8001/mcp" -ForegroundColor Gray
Write-Host "  Registry    http://127.0.0.1:8002/mcp" -ForegroundColor Gray
Write-Host "  GitHub      http://127.0.0.1:8003/mcp" -ForegroundColor Gray
Write-Host "  Monitor     SSE（见 FastMCP 配置）" -ForegroundColor Gray
Write-Host "  Defence     SSE（见 FastMCP 配置）" -ForegroundColor Gray

Write-Host "`n================================================" -ForegroundColor Green
Write-Host "  MCP 已在后台运行（最小化窗口）" -ForegroundColor Green
Write-Host "  停止: powershell -File `"$PSScriptRoot\stop_mcp_all.ps1`"" -ForegroundColor Gray
Write-Host "================================================`n" -ForegroundColor Green
