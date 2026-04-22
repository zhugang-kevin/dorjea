#Requires -Version 5.1
# 停止 AgentCore MCP 服务（PID 文件 + 端口清扫）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $RepoRoot "mcp_pids.txt"

if (Test-Path -LiteralPath $pidFile) {
    $raw = Get-Content -LiteralPath $pidFile -Raw
    $pids = $raw -split "[,\s]+" | Where-Object { $_ -match "^\d+$" }
    foreach ($p in $pids) {
        try {
            Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
            Write-Host "已停止 PID $p" -ForegroundColor Green
        } catch {}
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

foreach ($port in @(8001, 8002, 8003, 8004, 8005)) {
    netstat -ano 2>$null | Select-String ":$port\s" | ForEach-Object {
        $line = $_.Line.Trim() -split "\s+"
        $procId = $line[-1]
        if ($procId -match "^\d+$" -and $procId -ne "0") {
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "MCP 服务已全部停止" -ForegroundColor Red
