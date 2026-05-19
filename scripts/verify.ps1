# verify.ps1 - daily project verification + release gate runner
param(
    [switch]$SkipPytest,
    [switch]$SkipFrontend,
    [switch]$SkipCloneVerify,
    [switch]$StrictFrontend,
    [switch]$ReleaseCandidate
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot
$errors = 0
$verificationStart = [datetime]::UtcNow
$criticalFilesPassed = $true
$importsPassed = $true
$dbCheckPassed = $true
$assurancePassed = $true
$backupRestorePassed = $true
$todoCheckPassed = $true
$pytestPassed = $false
$frontendLintPassed = $false
$frontendBuildPassed = $false
$cloneVerifyPassed = $false
$apiHealthPassed = $false
$runStamp = $verificationStart.ToString("yyyyMMdd-HHmmss")
$runLogDir = Join-Path -Path $RepoRoot -ChildPath ("logs\release_rehearsals\run-" + $runStamp)
New-Item -ItemType Directory -Path $runLogDir -Force | Out-Null

if ($ReleaseCandidate) {
    $StrictFrontend = $true
    if ($SkipPytest -or $SkipFrontend -or $SkipCloneVerify) {
        Write-Host "ReleaseCandidate mode forbids skip flags. Remove SkipPytest/SkipFrontend/SkipCloneVerify." -ForegroundColor Red
        exit 1
    }
}
$WindowsVenvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
$LinuxVenvPython = Join-Path $RepoRoot "venv\bin\python"
if (Test-Path -LiteralPath $WindowsVenvPython) {
    $PythonExe = $WindowsVenvPython
} elseif (Test-Path -LiteralPath $LinuxVenvPython) {
    throw "Detected a Linux-style virtualenv at $LinuxVenvPython. Rebuild the virtualenv for Windows before running verification."
} else {
    $PythonExe = "python"
}

function Test-ProjectFile {
    param([string]$FullName)
    return (
        $FullName -notmatch '\\venv(\\|$)' -and
        $FullName -notmatch '\\venv_linux_backup(\\|$)' -and
        $FullName -notmatch '\\node_modules(\\|$)' -and
        $FullName -notmatch '\\frontend\\node_modules(\\|$)' -and
        $FullName -notmatch '\\frontend\\\.next(\\|$)' -and
        $FullName -notmatch '\\frontend\\\.next-runtime(\\|$)' -and
        $FullName -notmatch '\\__pycache__(\\|$)' -and
        $FullName -notmatch '\\\.git(\\|$)'
    )
}

Write-Host "Guixin AgentCore - daily verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n[1] Checking critical files..." -ForegroundColor Yellow
$criticalFiles = @(
    "AGENTS.md", ".cursor\rules\00-global.mdc", ".env", ".env.example", "requirements.txt",
    "ai-system\project_state.json", "ai-system\workflow.json", "ai-system\controller.py",
    "ai-system\router.py", "ai-system\validator.py", "ai-system\health_check.py", "system_architecture.md",
    "agents\meta_agent\models.py", "agents\meta_agent\state.py", "agents\meta_agent\nodes.py",
    "agents\meta_agent\graph.py", "agents\meta_agent\api.py", "agents\meta_agent\registry.py",
    "agents\meta_agent\audit_logger.py", "agents\meta_agent\build_contract.py",
    "agents\meta_agent\model_handoff.py", "agents\meta_agent\assurance.py", "agents\runtime\ai_clients.py",
    "agents\runtime\task_queue.py", "agents\runtime\worker_runner.py",
    "scripts\check_foundation.py", "scripts\assurance_check.py", "scripts\backup_restore_verify.py",
    "tools\mcp\filesystem_server\server.py", "tools\mcp\registry_server\server.py",
    "memory\aifactory.db", "memory\schema.sql", "scripts\check_system_state.py", "scripts\start_all.ps1",
    "scripts\start_worker.ps1", "docs\enterprise_architecture.md", "infra\docker-compose.enterprise.yml",
    "docs\release_gate.md", "docs\release_rehearsal_report.md"
)
foreach ($name in $criticalFiles) {
    $full = Join-Path -Path $RepoRoot -ChildPath $name
    if (Test-Path -LiteralPath $full) { Write-Host "  OK: $name" -ForegroundColor Green }
    else {
        Write-Host "  MISSING: $name" -ForegroundColor Red
        $errors++
        $criticalFilesPassed = $false
    }
}

Write-Host "`n[2] Checking common secret samples..." -ForegroundColor Yellow
$secretPatterns = @("sk-ant-", "sk-proj-", "ANTHROPIC_API_KEY=sk", "OPENAI_API_KEY=sk")
$secretFound = $false
$scanFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { (Test-ProjectFile $_.FullName) -and ($_.Extension -match '\.(py|ps1|md|ts|tsx|js|json|env)$') }
foreach ($pattern in $secretPatterns) {
    foreach ($file in $scanFiles) {
        if ($file.Name -match 'verify|write_verify|fix_') { continue }
        $c = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($null -eq $c) { continue }
        if ($c -match [regex]::Escape($pattern)) {
            Write-Host "  Suspicious content: $($file.FullName)" -ForegroundColor Red
            $errors++
            $secretFound = $true
        }
    }
}
if (-not $secretFound) { Write-Host "  OK: no common external key samples found" -ForegroundColor Green }

Write-Host "`n[3] Checking Python imports..." -ForegroundColor Yellow
$imports = @(
    "from agents.meta_agent.models import TaskSpec, AgentSpec, FounderReport",
    "from agents.meta_agent.state import MetaAgentState",
    "from agents.meta_agent.nodes import parse_request, return_report",
    "from agents.meta_agent.graph import meta_agent_graph",
    "from agents.meta_agent.api import app",
    "from agents.runtime.ai_clients import PrimaryChatClient, AIChatRequest",
    "from agents.meta_agent.build_contract import load_build_state",
    "from agents.meta_agent.model_handoff import get_model_guidance",
    "from agents.runtime.task_queue import task_queue"
)
foreach ($import in $imports) {
    $result = & $PythonExe -c "$import; print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and ($result | Select-Object -Last 1) -eq "OK") {
        Write-Host "  OK: $import" -ForegroundColor Green
    } else {
        Write-Host "  FAILED: $import" -ForegroundColor Red
        Write-Host "    $result" -ForegroundColor DarkRed
        $errors++
        $importsPassed = $false
    }
}

Write-Host "`n[4] Checking database..." -ForegroundColor Yellow
$dbScript = Join-Path -Path $RepoRoot -ChildPath "memory\check_db_verify.py"
$dbResult = & $PythonExe $dbScript 2>&1
if ($dbResult -match "^OK:") {
    Write-Host "  OK: database is reachable. Tables: $($dbResult -replace '^OK:','')" -ForegroundColor Green
} else {
    Write-Host "  FAILED: $dbResult" -ForegroundColor Red
    $errors++
    $dbCheckPassed = $false
}
$foundationScript = Join-Path -Path $RepoRoot -ChildPath "scripts\check_foundation.py"
$foundationResult = & $PythonExe $foundationScript 2>&1
if ($foundationResult -match "^READY$") {
    Write-Host "  OK: project foundation charter is present" -ForegroundColor Green
} else {
    Write-Host "  FAILED: $foundationResult" -ForegroundColor Red
    $errors++
    $dbCheckPassed = $false
}

Write-Host "`n[5] Checking assurance and backup verification..." -ForegroundColor Yellow
$assuranceScript = Join-Path -Path $RepoRoot -ChildPath "scripts\assurance_check.py"
$assuranceResult = & $PythonExe $assuranceScript 2>&1
if ($assuranceResult -match "^READY$") {
    Write-Host "  OK: assurance checks passed" -ForegroundColor Green
} else {
    Write-Host "  FAILED: $assuranceResult" -ForegroundColor Red
    $errors++
    $assurancePassed = $false
}
$backupScript = Join-Path -Path $RepoRoot -ChildPath "scripts\backup_restore_verify.py"
$backupResult = & $PythonExe $backupScript 2>&1
if ($backupResult -match "^READY$") {
    Write-Host "  OK: backup/restore verification passed" -ForegroundColor Green
} else {
    Write-Host "  FAILED: $backupResult" -ForegroundColor Red
    $errors++
    $backupRestorePassed = $false
}

Write-Host "`n[6] Checking TODO comments..." -ForegroundColor Yellow
$pyFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -Filter "*.py" |
    Where-Object { Test-ProjectFile $_.FullName }
$todoFound = $false
foreach ($file in $pyFiles) {
    $lines = Get-Content -LiteralPath $file.FullName
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*#.*(TODO|FIXME)") {
            $relativePath = $file.FullName.Substring($RepoRoot.Length + 1)
            Write-Host ("  TODO: {0} line {1}" -f $relativePath, ($i + 1)) -ForegroundColor Red
            $errors++
            $todoFound = $true
            $todoCheckPassed = $false
        }
    }
}
if (-not $todoFound) { Write-Host "  OK: no TODO/FIXME comments found" -ForegroundColor Green }

Write-Host "`n[7] Running backend tests (pytest)..." -ForegroundColor Yellow
if ($SkipPytest) {
    Write-Host "  SKIP: pytest (requested)" -ForegroundColor Yellow
} else {
    $pytestResult = & $PythonExe -m pytest -q 2>&1
    Set-Content -LiteralPath (Join-Path $runLogDir "07-pytest.log") -Value ($pytestResult | Out-String) -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: pytest passed" -ForegroundColor Green
        $pytestPassed = $true
    } else {
        Write-Host "  FAILED: pytest failed" -ForegroundColor Red
        Write-Host "    $pytestResult" -ForegroundColor DarkRed
        $errors++
    }
}

Write-Host "`n[8] Running frontend lint/build..." -ForegroundColor Yellow
if ($SkipFrontend) {
    Write-Host "  SKIP: frontend lint/build (requested)" -ForegroundColor Yellow
    if ($StrictFrontend) {
        Write-Host "  FAILED: strict frontend mode requires lint/build to run." -ForegroundColor Red
        $errors++
    }
} else {
    $frontendPath = Join-Path -Path $RepoRoot -ChildPath "frontend"
    if (-not (Test-Path -LiteralPath $frontendPath)) {
        Write-Host "  FAILED: frontend directory missing at $frontendPath" -ForegroundColor Red
        $errors++
    } else {
        Push-Location -LiteralPath $frontendPath
        try {
            $lintResult = & npm run lint 2>&1
            Set-Content -LiteralPath (Join-Path $runLogDir "08-frontend-lint.log") -Value ($lintResult | Out-String) -Encoding UTF8
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK: frontend lint passed" -ForegroundColor Green
                $frontendLintPassed = $true
            } else {
                Write-Host "  FAILED: frontend lint failed" -ForegroundColor Red
                Write-Host "    $lintResult" -ForegroundColor DarkRed
                $errors++
            }

            $buildResult = & npm run build 2>&1
            Set-Content -LiteralPath (Join-Path $runLogDir "08-frontend-build.log") -Value ($buildResult | Out-String) -Encoding UTF8
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK: frontend build passed" -ForegroundColor Green
                $frontendBuildPassed = $true
            } else {
                Write-Host "  FAILED: frontend build failed" -ForegroundColor Red
                Write-Host "    $buildResult" -ForegroundColor DarkRed
                $errors++
            }
        } finally {
            Pop-Location
        }
    }
}

Write-Host "`n[9] Checking API health endpoint..." -ForegroundColor Yellow
try {
    $healthScript = @"
from fastapi.testclient import TestClient
from agents.meta_agent.api import app
client = TestClient(app)
r = client.get('/health')
status = r.json().get('status', '')
if r.status_code == 200 and status in {'healthy', 'ok', 'alert'}:
    print('OK')
else:
    print(f'BAD status_code={r.status_code} status={status}')
    raise SystemExit(1)
"@
    $healthResult = $healthScript | & $PythonExe - 2>&1
    Set-Content -LiteralPath (Join-Path $runLogDir "09-health-probe.log") -Value ($healthResult | Out-String) -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: /health returned valid response" -ForegroundColor Green
        $apiHealthPassed = $true
    } else {
        Write-Host "  FAILED: /health probe failed" -ForegroundColor Red
        Write-Host "    $healthResult" -ForegroundColor DarkRed
        $errors++
    }
} catch {
    Write-Host "  FAILED: /health probe failed with exception" -ForegroundColor Red
    Write-Host "    $($_.Exception.Message)" -ForegroundColor DarkRed
    $errors++
}

Write-Host "`n[10] Running clone verification..." -ForegroundColor Yellow
if ($SkipCloneVerify) {
    Write-Host "  SKIP: clone verification (requested)" -ForegroundColor Yellow
} else {
    $workspaceRoot = Split-Path -Parent $RepoRoot
    $cloneVerifyScript = Join-Path -Path $workspaceRoot -ChildPath "clone_verify.ps1"
    if (-not (Test-Path -LiteralPath $cloneVerifyScript)) {
        Write-Host "  FAILED: clone verifier missing at $cloneVerifyScript" -ForegroundColor Red
        $errors++
    } else {
        $cloneResult = & $cloneVerifyScript 2>&1
        Set-Content -LiteralPath (Join-Path $runLogDir "10-clone-verify.log") -Value ($cloneResult | Out-String) -Encoding UTF8
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: clone verification passed" -ForegroundColor Green
            $cloneVerifyPassed = $true
        } else {
            Write-Host "  FAILED: clone verification failed" -ForegroundColor Red
            Write-Host "    $cloneResult" -ForegroundColor DarkRed
            $errors++
        }
        Set-Location -LiteralPath $RepoRoot
    }
}

Write-Host "`n[11] Writing release rehearsal evidence..." -ForegroundColor Yellow
$verificationEnd = [datetime]::UtcNow
$reportPath = Join-Path -Path $RepoRoot -ChildPath ("logs\release_rehearsals\rehearsal-" + $verificationEnd.ToString("yyyyMMdd-HHmmss") + ".json")
$reportScript = Join-Path -Path $RepoRoot -ChildPath "scripts\write_rehearsal_report.py"
$reportArgs = @(
    $reportScript,
    "--repo-root", $RepoRoot,
    "--output", $reportPath,
    "--errors", "$errors",
    "--start-iso", $verificationStart.ToString("o"),
    "--end-iso", $verificationEnd.ToString("o")
)
if ($SkipPytest) { $reportArgs += "--skip-pytest" }
if ($SkipFrontend) { $reportArgs += "--skip-frontend" }
if ($SkipCloneVerify) { $reportArgs += "--skip-clone-verify" }
if ($pytestPassed) { $reportArgs += "--pytest-passed" }
if ($frontendLintPassed) { $reportArgs += "--frontend-lint-passed" }
if ($frontendBuildPassed) { $reportArgs += "--frontend-build-passed" }
if ($cloneVerifyPassed) { $reportArgs += "--clone-verify-passed" }
if ($apiHealthPassed) { $reportArgs += "--api-health-passed" }
if ($dbCheckPassed) { $reportArgs += "--db-check-passed" }
if ($backupRestorePassed) { $reportArgs += "--backup-restore-passed" }
if ($assurancePassed) { $reportArgs += "--assurance-passed" }
if ($importsPassed) { $reportArgs += "--imports-passed" }
if ($criticalFilesPassed) { $reportArgs += "--critical-files-passed" }
if ($todoCheckPassed) { $reportArgs += "--todo-check-passed" }

$reportResult = & $PythonExe @reportArgs 2>&1
Set-Content -LiteralPath (Join-Path $runLogDir "11-report-generator.log") -Value ($reportResult | Out-String) -Encoding UTF8
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: rehearsal report written to $reportPath" -ForegroundColor Green
} else {
    Write-Host "  FAILED: unable to write rehearsal report" -ForegroundColor Red
    Write-Host "    $reportResult" -ForegroundColor DarkRed
    $errors++
}

Set-Content -LiteralPath (Join-Path $runLogDir "01-critical-files.log") -Value ("critical_files_passed=" + $criticalFilesPassed) -Encoding UTF8
Set-Content -LiteralPath (Join-Path $runLogDir "03-imports.log") -Value ("imports_passed=" + $importsPassed) -Encoding UTF8
Set-Content -LiteralPath (Join-Path $runLogDir "04-database.log") -Value ("db_check_passed=" + $dbCheckPassed) -Encoding UTF8
Set-Content -LiteralPath (Join-Path $runLogDir "05-assurance-backup.log") -Value (
    "assurance_passed=" + $assurancePassed + [Environment]::NewLine +
    "backup_restore_passed=" + $backupRestorePassed
) -Encoding UTF8
Set-Content -LiteralPath (Join-Path $runLogDir "06-todo-scan.log") -Value ("todo_check_passed=" + $todoCheckPassed) -Encoding UTF8

Write-Host "`n========================================" -ForegroundColor Cyan
if ($errors -eq 0) { Write-Host "Verification passed - 0 errors" -ForegroundColor Green }
else { Write-Host "Verification failed - $errors issue(s)" -ForegroundColor Red }
Write-Host "========================================" -ForegroundColor Cyan

if ($errors -gt 0) {
    exit 1
}
