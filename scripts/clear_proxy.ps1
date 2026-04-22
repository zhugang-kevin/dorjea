# clear_proxy.ps1 - Local environment cleanup for AgentCore
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:all_proxy = ""
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"

foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
    [System.Environment]::SetEnvironmentVariable($name, $null, "Process")
}

# Clear Git proxy for the current machine if it was previously pinned to a local forward proxy.
git config --global --unset-all http.proxy 2>$null
git config --global --unset-all https.proxy 2>$null
git config --global --unset-all http.sslVerify 2>$null

# Load all env vars from .env file safely - never hardcode secrets
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.+)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}
Write-Host "Local proxy variables cleared. localhost calls will bypass proxy." -ForegroundColor Green

# Helper function for local API calls - always bypasses proxy
function Invoke-LocalAPI {
    param($Uri, $Method = "GET", $Body = $null, $ContentType = "application/json")
    if ($Body) {
        return Invoke-RestMethod -Uri $Uri -Method $Method -Body $Body -ContentType $ContentType -NoProxy
    }
    return Invoke-RestMethod -Uri $Uri -Method $Method -NoProxy
}
Write-Host "Local API helper loaded. Use Invoke-LocalAPI instead of Invoke-RestMethod." -ForegroundColor Cyan
