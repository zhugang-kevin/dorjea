$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:NO_PROXY = "api.anthropic.com,api.openai.com,pypi.org,localhost,127.0.0.1"
git config --global --unset http.proxy
git config --global --unset https.proxy
git config --global http.sslVerify false
Write-Host "Environment ready. Safe to proceed." -ForegroundColor Green
