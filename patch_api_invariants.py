import re

PATH = r"E:\Dorjea\Dorjea\agents\meta_agent\api.py"

with open(PATH, "r", encoding="utf-8") as f:
    c = f.read()

# 1. Add import after validation_gates import
OLD_IMPORT = "from agents.meta_agent.validation_gates import run_all_gates, get_gate_summary"
NEW_IMPORT = (
    "from agents.meta_agent.validation_gates import run_all_gates, get_gate_summary\n"
    "from agents.meta_agent.architecture_invariants import check_invariants, get_invariant_list, VALID_DEPARTMENTS"
)
c = c.replace(OLD_IMPORT, NEW_IMPORT, 1)

# 2. Add endpoint before @app.get("/health")
OLD_HEALTH = '@app.get("/health")'
NEW_ENDPOINT = (
    '@app.get("/agents/invariants")\n'
    'def list_invariants() -> dict:\n'
    '    """Return all 25 architecture invariants."""\n'
    '    return {"invariants": get_invariant_list(), "total": 25}\n'
    '\n\n'
    '@app.get("/health")'
)
c = c.replace(OLD_HEALTH, NEW_ENDPOINT, 1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(c)

print("Patched api.py")
assert "from agents.meta_agent.architecture_invariants import check_invariants" in c
assert '/agents/invariants' in c
assert "get_invariant_list" in c
print("All assertions passed.")
