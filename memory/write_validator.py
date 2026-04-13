content = """
from pathlib import Path
from agents.meta_agent.manifest_manager import validate_manifest


REQUIRED_AGENT_FIELDS = [
    "agent_name",
    "version",
    "mission",
    "responsibilities",
    "non_responsibilities",
    "allowed_tools",
    "token_budget",
    "default_model",
    "fallback_model",
    "escalation_triggers",
    "memory_policy",
    "department",
]

MAX_RECURSION_DEPTH = 3
MAX_TASK_CHAIN = 10
MAX_TOKENS_PER_TASK = 20000


def validate_agent_spec(agent_spec):
    errors = []
    for field in REQUIRED_AGENT_FIELDS:
        if not getattr(agent_spec, field, None):
            errors.append("Missing required field: " + field)
    if len(agent_spec.responsibilities) < 3:
        errors.append("Agent must have at least 3 responsibilities")
    if len(agent_spec.non_responsibilities) < 2:
        errors.append("Agent must have at least 2 non_responsibilities")
    if len(agent_spec.escalation_triggers) < 2:
        errors.append("Agent must have at least 2 escalation_triggers")
    if agent_spec.token_budget > MAX_TOKENS_PER_TASK:
        errors.append("Token budget exceeds maximum: " + str(MAX_TOKENS_PER_TASK))
    if not agent_spec.agent_name.replace("_", "").isalnum():
        errors.append("Agent name must be snake_case alphanumeric only")
    return len(errors) == 0, errors


def validate_generated_files(agent_name):
    errors = []
    code_path = Path("agents/generated") / (agent_name + ".py")
    config_path = Path("agents/generated") / (agent_name + ".yaml")
    spec_path = Path("agents/specs") / (agent_name + ".yaml")
    if not code_path.exists():
        errors.append("Missing generated code file: " + str(code_path))
    if not config_path.exists():
        errors.append("Missing generated config file: " + str(config_path))
    if not spec_path.exists():
        errors.append("Missing spec file: " + str(spec_path))
    if code_path.exists():
        code = code_path.read_text(encoding="utf-8")
        if len(code.strip()) < 50:
            errors.append("Generated code file is too short — likely empty")
    return len(errors) == 0, errors


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
    manifest_ok, manifest_msg = validate_manifest(agent_spec.agent_name)
    if not manifest_ok:
        all_errors.append(manifest_msg)
    if registry_list:
        loop_ok, loop_msg = validate_no_circular_dependency(
            agent_spec.agent_name, registry_list
        )
        if not loop_ok:
            all_errors.append(loop_msg)
    return len(all_errors) == 0, all_errors
"""

with open("agents/meta_agent/architecture_validator.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("architecture_validator.py created")
