import json, subprocess, sys
from datetime import datetime
from pathlib import Path
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

TRACKED_PACKAGES = [
    'anthropic', 'openai', 'langgraph', 'fastapi', 'pydantic',
    'uvicorn', 'langsmith', 'httpx', 'psutil', 'pyyaml',
]

MODELS_REGISTRY = {
    'anthropic': {'current': 'claude-sonnet-4-6', 'family': 'claude-4', 'check_url': 'https://api.anthropic.com'},
    'openai': {'current': 'gpt-5', 'family': 'gpt-5', 'check_url': 'https://api.openai.com'},
    'deepseek': {'current': 'deepseek-chat', 'family': 'deepseek', 'check_url': 'https://api.deepseek.com'},
}

VERSION_LOG = Path('logs/version_checks.jsonl')

def get_installed_version(package):
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'show', package], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.startswith('Version:'):
                return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return 'unknown'

def get_latest_version(package):
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'index', 'versions', package], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if 'Available versions:' in line:
                versions = line.split(':', 1)[1].strip().split(',')
                return versions[0].strip()
    except Exception:
        pass
    return 'unknown'

def check_all_versions():
    results = []
    updates_available = []
    for pkg in TRACKED_PACKAGES:
        installed = get_installed_version(pkg)
        latest = get_latest_version(pkg)
        needs_update = installed != latest and latest != 'unknown'
        if needs_update:
            updates_available.append({'package': pkg, 'installed': installed, 'latest': latest})
        results.append({'package': pkg, 'installed': installed, 'latest': latest, 'up_to_date': not needs_update})
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'packages_checked': len(results),
        'updates_available': len(updates_available),
        'updates': updates_available,
        'all_packages': results,
    }
    VERSION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(VERSION_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(report) + chr(10))
    write_audit_entry(AuditEntry(agent_id='version_checker', task_id='check', action='VERSION_CHECK_COMPLETE', details={'updates_available': len(updates_available)}, success=True))
    return report

def print_version_report():
    print('Checking versions...')
    report = check_all_versions()
    print('Packages checked: ' + str(report['packages_checked']))
    if report['updates_available'] == 0:
        print('All packages up to date.')
    else:
        print('Updates available: ' + str(report['updates_available']))
        for u in report['updates']:
            print('  ' + u['package'] + ': ' + u['installed'] + ' -> ' + u['latest'])
    return report
