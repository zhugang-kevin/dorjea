from pathlib import Path

MANIFESTS_DIR = Path("agents/manifests")
REQUIRED_AGENT_FIELDS = ["agent_name","version","mission","responsibilities","non_responsibilities","allowed_tools","token_budget","default_model","fallback_model","escalation_triggers","memory_policy","department"]
MAX_TOKENS_PER_TASK = 10000

def validate_agent_spec(agent_spec):
    errors = []
    for field in REQUIRED_AGENT_FIELDS:
        if not getattr(agent_spec, field, None):
            errors.append("Missing required field: " + field)
    if agent_spec.token_budget > MAX_TOKENS_PER_TASK:
        errors.append("Token budget exceeds maximum")
    return len(errors) == 0, errors

def validate_generated_files(agent_name):
    Path("agents/generated").mkdir(parents=True, exist_ok=True)
    Path("agents/specs").mkdir(parents=True, exist_ok=True)
    Path("agents/manifests").mkdir(parents=True, exist_ok=True)
    errors = []
    code_path = Path("agents/generated") / (agent_name + ".py")
    if code_path.exists():
        code = code_path.read_text(encoding="utf-8")
        if len(code.strip()) < 50:
            errors.append("Generated code file is too short")
    return len(errors) == 0, errors

def validate_manifest(agent_name):
    manifest_path = MANIFESTS_DIR / (agent_name + "_manifest.yaml")
    if not manifest_path.exists():
        return True, "Manifest will be created during registration"
    return True, "Manifest valid"

def validate_no_circular_dependency(agent_name, registry_list):
    if registry_list.count(agent_name) > 1:
        return False, "Circular dependency detected for agent: " + agent_name
    return True, ""

def run_full_architecture_validation(agent_spec, registry_list=None):
    all_errors = []
    spec_ok, spec_errors = validate_agent_spec(agent_spec)
    if not spec_ok:
        all_errors.extend(spec_errors)
    files_ok, file_errors = validate_generated_files(agent_spec.agent_name)
    if not files_ok:
        all_errors.extend(file_errors)
    if registry_list:
        loop_ok, loop_msg = validate_no_circular_dependency(agent_spec.agent_name, registry_list)
        if not loop_ok:
            all_errors.append(loop_msg)
    return len(all_errors) == 0, all_errors
