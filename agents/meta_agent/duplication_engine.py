import shutil, yaml, os
from pathlib import Path
from datetime import datetime

MASTER_DIR = Path('E:/Dorjea')
CLONE_CONFIGS = {
    'marketing':   {'specialization':'marketing',   'allowed_departments':['marketing','sales','content','brand'],        'clone_dir':'E:/Dorjea_Marketing',   'port':8010},
    'engineering': {'specialization':'engineering', 'allowed_departments':['engineering','devops','qa','security'],       'clone_dir':'E:/Dorjea_Engineering', 'port':8011},
    'research':    {'specialization':'research',    'allowed_departments':['research','data','analytics','intelligence'], 'clone_dir':'E:/Dorjea_Research',    'port':8012},
    'operations':  {'specialization':'operations',  'allowed_departments':['operations','support','finance','hr','legal'],'clone_dir':'E:/Dorjea_Operations',  'port':8013},
    'strategy':    {'specialization':'strategy',    'allowed_departments':['strategy','planning','product','innovation'], 'clone_dir':'E:/Dorjea_Strategy',    'port':8014},
}
EXCLUDE = {'venv','__pycache__','.git','node_modules','logs','agents/generated','agents/manifests','memory/agent_memory','.pytest_cache'}

def should_exclude(path, base):
    rel = str(path.relative_to(base))
    return any(rel.startswith(e) for e in EXCLUDE) or rel in {'memory/aifactory.db','.env'}

def list_clones():
    for name, c in CLONE_CONFIGS.items():
        status = 'EXISTS' if Path(c['clone_dir']).exists() else 'not created'
        print('  ' + name + ' -> port ' + str(c['port']) + ' [' + status + ']')

def clone_meta_agent(specialization):
    if specialization not in CLONE_CONFIGS: return False
    config = CLONE_CONFIGS[specialization]
    clone_dir = Path(config['clone_dir'])
    if clone_dir.exists(): print('Already exists: ' + str(clone_dir)); return False
    clone_dir.mkdir(parents=True, exist_ok=True)
    for item in MASTER_DIR.rglob('*'):
        if should_exclude(item, MASTER_DIR): continue
        rel = item.relative_to(MASTER_DIR)
        dest = clone_dir / rel
        if item.is_dir(): dest.mkdir(parents=True, exist_ok=True)
        elif item.is_file(): dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(item, dest)
    for d in ['logs','agents/generated','agents/manifests','agents/specs','memory/agent_memory','logs/reproductions','evals/reports']:
        (clone_dir / d).mkdir(parents=True, exist_ok=True)
    policy_path = clone_dir / 'agents/meta_agent/policy.yaml'
    if policy_path.exists():
        with open(policy_path, 'r', encoding='utf-8') as f: policy = yaml.safe_load(f) or {}
        policy['meta_agent_name'] = 'meta-agent-' + specialization
        policy['specialization'] = specialization
        policy['allowed_departments'] = config['allowed_departments']
        policy['api_port'] = config['port']
        with open(policy_path, 'w', encoding='utf-8') as f: yaml.dump(policy, f, default_flow_style=False)
    nl = chr(10)
    start = 'Set-Location ' + str(clone_dir) + nl
    start += '.\\venv\\Scripts\\Activate.ps1' + nl
    start += '. .\\scripts\\clear_proxy.ps1' + nl
    start += 'python memory\\init_db.py' + nl
    start += 'uvicorn agents.meta_agent.api:app --reload --host 127.0.0.1 --port ' + str(config['port']) + nl
    with open(clone_dir / 'start.ps1', 'w', encoding='utf-8') as f: f.write(start)
    with open(clone_dir / '.env.template', 'w', encoding='utf-8') as f:
        f.write('ANTHROPIC_API_KEY=your_key_here' + nl + 'PRIMARY_MODEL=claude-sonnet-4-6' + nl + 'DATABASE_URL=sqlite:///./memory/aifactory.db' + nl + 'META_AGENT_SPECIALIZATION=' + specialization + nl + 'META_AGENT_PORT=' + str(config['port']) + nl)
    print('Clone created: ' + specialization + ' at ' + str(clone_dir))
    return True

def clone_all():
    for spec in CLONE_CONFIGS: clone_meta_agent(spec)
