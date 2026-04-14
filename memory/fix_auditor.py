content = """
import json
from datetime import datetime
from agents.meta_agent.registry import list_agents, get_agent

DNA_COMPONENTS = [
    'mission', 'responsibilities', 'non_responsibilities',
    'allowed_tools', 'escalation_triggers', 'token_budget',
    'default_model', 'fallback_model', 'memory_policy', 'department',
]

DNA_QUALITY_CHECKS = {
    'mission': lambda v: len(str(v)) > 50,
    'responsibilities': lambda v: (isinstance(v, list) and len(v) >= 5) or (isinstance(v, str) and len(v) > 20),
    'non_responsibilities': lambda v: (isinstance(v, list) and len(v) >= 3) or (isinstance(v, str) and len(v) > 20),
    'escalation_triggers': lambda v: (isinstance(v, list) and len(v) >= 2) or (isinstance(v, str) and len(v) > 10),
    'allowed_tools': lambda v: bool(v),
}

def parse_field(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            if ',' in value:
                return [v.strip() for v in value.split(',') if v.strip()]
            return value
    return value

def audit_agent(agent_name):
    agent = get_agent(agent_name)
    if not agent:
        return {'agent': agent_name, 'score': 0, 'issues': ['Agent not found'], 'grade': 'F'}
    issues = []
    passed = 0
    total = len(DNA_COMPONENTS)
    for component in DNA_COMPONENTS:
        raw_value = agent.get(component)
        value = parse_field(raw_value)
        if not value:
            issues.append('Missing: ' + component)
            continue
        if component in DNA_QUALITY_CHECKS:
            if DNA_QUALITY_CHECKS[component](value):
                passed += 1
            else:
                issues.append('Weak: ' + component)
        else:
            passed += 1
    score = round(passed / total * 100, 1)
    grade = 'A' if score >= 90 else 'B' if score >= 80 else 'C' if score >= 70 else 'D' if score >= 60 else 'F'
    return {'agent': agent_name, 'score': score, 'grade': grade, 'issues': issues, 'passed': passed, 'total': total}

def audit_all_agents():
    agents = list_agents(status='active')
    results = []
    needs_regeneration = []
    for agent in agents:
        name = agent.get('name', '')
        result = audit_agent(name)
        results.append(result)
        if result['score'] < 80:
            needs_regeneration.append(name)
    avg = round(sum(r['score'] for r in results) / len(results), 1) if results else 0
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'total_agents': len(results),
        'average_score': avg,
        'needs_regeneration': needs_regeneration,
        'results': sorted(results, key=lambda x: x['score']),
    }
"""

with open("agents/meta_agent/agent_auditor.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("agent_auditor.py fixed")
