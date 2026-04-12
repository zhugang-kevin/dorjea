
$env:HTTP_PROXY = ""

$env:HTTPS_PROXY = ""

$env:NO_PROXY = "api.anthropic.com,api.openai.com,github.com,pypi.org,localhost,127.0.0.1"

$env:ANTHROPIC_BASE_URL = "https://api.anthropic.com"

Write-Host "Proxy cleared. Safe to proceed." -ForegroundColor Green

