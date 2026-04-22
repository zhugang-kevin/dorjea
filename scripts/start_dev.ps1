# start_dev.ps1 — Start all AgentCore services
# Run from anywhere: F:\AgentCore\AgentCore\scripts\start_dev.ps1

$root     = "F:\AgentCore\AgentCore"
$frontend = "F:\AgentCore\AgentCore-dashboard"
$venv     = "$root\venv\Scripts\Activate.ps1"
$apiPort  = if ($env:API_PORT) { $env:API_PORT } else { "8000" }

# Clear proxy
$env:HTTP_PROXY = $env:HTTPS_PROXY = $env:ALL_PROXY = ""
$env:http_proxy = $env:https_proxy = $env:all_proxy = ""

Write-Host "Starting AgentCore services..." -ForegroundColor Cyan
Write-Host "Backend port: $apiPort" -ForegroundColor DarkCyan

# FastAPI backend
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$root'; . .\scripts\clear_proxy.ps1; & '$venv'; `$env:API_PORT='$apiPort'; uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port $apiPort"

Start-Sleep -Seconds 2

# Filesystem MCP — port 8001
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$root'; & '$venv'; python tools\mcp\filesystem_server\server.py"

Start-Sleep -Seconds 1

# Registry MCP — port 8002
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$root'; & '$venv'; python tools\mcp\registry_server\server.py"

Start-Sleep -Seconds 1

# Next.js frontend — port 3000
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$frontend'; npm run dev"

Write-Host ""
Write-Host "All services started:" -ForegroundColor Green
Write-Host "  FastAPI:        http://127.0.0.1:$apiPort" -ForegroundColor White
Write-Host "  FastAPI docs:   http://127.0.0.1:$apiPort/docs" -ForegroundColor White
Write-Host "  Filesystem MCP: http://127.0.0.1:8001" -ForegroundColor White
Write-Host "  Registry MCP:   http://127.0.0.1:8002" -ForegroundColor White
Write-Host "  Frontend:       http://127.0.0.1:3000" -ForegroundColor White
Write-Host ""
Write-Host "Health check: Invoke-RestMethod http://127.0.0.1:$apiPort/health -NoProxy" -ForegroundColor Yellow
