# clear_proxy.ps1 - Environment setup for Dorjea AI Factory
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:all_proxy = ""
git config --global http.proxy "http://127.0.0.1:10809"
git config --global https.proxy "http://127.0.0.1:10809"
git config --global http.sslVerify false

# Load all env vars from .env file safely - never hardcode secrets
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.+)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}
Write-Host "Environment ready. Safe to proceed." -ForegroundColor Green

# Helper function for local API calls - always bypasses proxy
function Invoke-LocalAPI {
    param($Uri, $Method = "GET", $Body = $null, $ContentType = "application/json")
    if ($Body) {
        return Invoke-RestMethod -Uri $Uri -Method $Method -Body $Body -ContentType $ContentType -NoProxy
    }
    return Invoke-RestMethod -Uri $Uri -Method $Method -NoProxy
}
Write-Host "Local API helper loaded. Use Invoke-LocalAPI instead of Invoke-RestMethod." -ForegroundColor Cyan
