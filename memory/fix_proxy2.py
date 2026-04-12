script = """# clear_proxy.ps1 - Environment setup for Dorjea AI Factory
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
"""

with open("scripts/clear_proxy.ps1", "w", encoding="utf-8") as f:
    f.write(script)
print("clear_proxy.ps1 fixed - no secrets")
