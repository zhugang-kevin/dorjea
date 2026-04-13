with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.prompts import ("
new = """from agents.meta_agent.manifest_manager import save_manifest
from agents.meta_agent.prompts import ("""

content = content.replace(old, new)

old_register = '''    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    spec_path = SPECS_DIR / f"{agent_spec.agent_name}.yaml"
    spec_path.write_text(spec_yaml or "", encoding="utf-8")

    result = db_register_agent('''

new_register = '''    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    spec_path = SPECS_DIR / f"{agent_spec.agent_name}.yaml"
    spec_path.write_text(spec_yaml or "", encoding="utf-8")

    manifest_path = save_manifest(agent_spec)
    _audit(state, "register_agent", f"Manifest saved: {manifest_path}")

    result = db_register_agent('''

content = content.replace(old_register, new_register)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with manifest generation")
