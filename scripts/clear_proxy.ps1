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
$env:ANTHROPIC_API_KEY = "sk-jXaPIlUOuMp6P043KlIpFkM6boA7c5AN7x9AQCtaWCzBlyl7"
$env:OPENAI_API_KEY = "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"
$env:PRIMARY_MODEL = "claude-sonnet-4-6"
$env:VERIFIER_MODEL = "gpt-4o"
$env:DATABASE_URL = "sqlite:///./memory/aifactory.db"
$env:ENVIRONMENT = "development"
$env:LOG_LEVEL = "INFO"
$env:MAX_TOKENS_PER_TASK = "20000"
Write-Host "Environment ready. Safe to proceed." -ForegroundColor Green
