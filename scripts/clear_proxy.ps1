$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:all_proxy = ""
git config --global http.proxy "http://127.0.0.1:10809"
git config --global https.proxy "http://127.0.0.1:10809"
git config --global http.sslVerify false
Write-Host "Environment ready. Safe to proceed." -ForegroundColor Green
