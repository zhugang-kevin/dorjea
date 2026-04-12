# start_dev.ps1 — Start all Dorjea AI Factory services
# Run this from E:\Dorjea with venv activated

Set-Location "E:\Dorjea"

# Clear proxy environment
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:all_proxy = ""

Write-Host "Starting Dorjea AI Factory services..." -ForegroundColor Cyan

# Start FastAPI backend on port 8000
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location 'E:\Dorjea'; .\venv\Scripts\Activate.ps1; uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port 8000"

Start-Sleep -Seconds 2

# Start Filesystem MCP server on port 8001
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location 'E:\Dorjea'; .\venv\Scripts\Activate.ps1; python tools\mcp\filesystem_server\server.py"

Start-Sleep -Seconds 1

# Start Registry MCP server on port 8002
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location 'E:\Dorjea'; .\venv\Scripts\Activate.ps1; python tools\mcp\registry_server\server.py"

Start-Sleep -Seconds 1

# Start GitHub MCP server on port 8003
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location 'E:\Dorjea'; .\venv\Scripts\Activate.ps1; python tools\mcp\github_server\server.py"

Write-Host ""
Write-Host "All services started:" -ForegroundColor Green
Write-Host "  FastAPI:        http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  FastAPI docs:   http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Filesystem MCP: http://127.0.0.1:8001" -ForegroundColor White
Write-Host "  Registry MCP:   http://127.0.0.1:8002" -ForegroundColor White
Write-Host "  GitHub MCP:     http://127.0.0.1:8003" -ForegroundColor White
Write-Host ""
Write-Host "Health check: Invoke-RestMethod http://127.0.0.1:8000/health" -ForegroundColor Yellow
