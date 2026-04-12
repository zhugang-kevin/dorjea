import re

env_vars = {}
with open(".env", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()

script = f"""# clear_proxy.ps1 - Environment setup for Dorjea AI Factory
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:all_proxy = ""
git config --global http.proxy "http://127.0.0.1:10809"
git config --global https.proxy "http://127.0.0.1:10809"
git config --global http.sslVerify false
$env:ANTHROPIC_API_KEY = "{env_vars.get('ANTHROPIC_API_KEY', '')}"
$env:OPENAI_API_KEY = "{env_vars.get('OPENAI_API_KEY', '')}"
$env:PRIMARY_MODEL = "{env_vars.get('PRIMARY_MODEL', 'claude-sonnet-4-6')}"
$env:VERIFIER_MODEL = "{env_vars.get('VERIFIER_MODEL', 'gpt-4o')}"
$env:DATABASE_URL = "{env_vars.get('DATABASE_URL', 'sqlite:///./memory/aifactory.db')}"
$env:ENVIRONMENT = "{env_vars.get('ENVIRONMENT', 'development')}"
$env:LOG_LEVEL = "{env_vars.get('LOG_LEVEL', 'INFO')}"
$env:MAX_TOKENS_PER_TASK = "{env_vars.get('MAX_TOKENS_PER_TASK', '20000')}"
Write-Host "Environment ready. Safe to proceed." -ForegroundColor Green
"""

with open("scripts/clear_proxy.ps1", "w", encoding="utf-8") as f:
    f.write(script)
print("clear_proxy.ps1 updated successfully")
