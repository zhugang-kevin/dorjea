$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:NO_PROXY = "api.anthropic.com,api.openai.com,pypi.org,localhost,127.0.0.1"
git config --global http.proxy "http://127.0.0.1:7890"
git config --global https.proxy "http://127.0.0.1:7890"
git config --global http.sslVerify false
Write-Host "Proxy cleared and Git proxy set. Safe to proceed." -ForegroundColor Green
