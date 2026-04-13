import os
import yaml
from pathlib import Path
from datetime import datetime


MANIFESTS_DIR = Path("agents/manifests")


def generate_manifest(agent_spec):
    manifest = {
        "agent_name": agent_spec.agent_name,
        "version": agent_spec.version,
        "created_at": datetime.utcnow().isoformat(),
        "role": {
            "description": agent_spec.mission,
            "department": agent_spec.department,
        },
        "permissions": {
            "allowed_tools": agent_spec.allowed_tools,
            "forbidden_tools": [
                "filesystem_delete",
                "system_exec",
                "database_admin",
                "config_editor",
                "core_modifier",
            ],
            "allowed_actions": agent_spec.responsibilities,
            "forbidden_actions": agent_spec.non_responsibilities,
        },
        "resource_limits": {
            "max_tokens_per_task": agent_spec.token_budget,
            "max_tasks_per_hour": 50,
            "max_runtime_seconds": 120,
            "max_recursion_depth": 3,
        },
        "governance": {
            "can_create_agents": False,
            "can_modify_core": False,
            "can_delete_logs": False,
            "can_modify_config": False,
            "requires_founder_approval": agent_spec.escalation_triggers,
        },
        "models": {
            "default_model": agent_spec.default_model,
            "fallback_model": agent_spec.fallback_model,
        },
        "memory_policy": agent_spec.memory_policy,
        "status": "active",
    }
    return manifest


def save_manifest(agent_spec):
    manifest = generate_manifest(agent_spec)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFESTS_DIR / (agent_spec.agent_name + "_manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
    return str(manifest_path)


def load_manifest(agent_name):
    manifest_path = MANIFESTS_DIR / (agent_name + "_manifest.yaml")
    if not manifest_path.exists():
        return None
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_manifest(agent_name):
    manifest = load_manifest(agent_name)
    if not manifest:
        return False, "Manifest not found for agent: " + agent_name
    required_keys = ["agent_name", "version", "permissions", "resource_limits", "governance"]
    for key in required_keys:
        if key not in manifest:
            return False, "Manifest missing required field: " + key
    if not manifest["permissions"].get("allowed_tools"):
        return False, "Manifest has no allowed_tools defined"
    return True, "Manifest valid"


def check_tool_permitted(agent_name, tool_name):
    manifest = load_manifest(agent_name)
    if not manifest:
        return False, "No manifest found"
    allowed = manifest.get("permissions", {}).get("allowed_tools", [])
    forbidden = manifest.get("permissions", {}).get("forbidden_tools", [])
    if tool_name in forbidden:
        return False, "Tool explicitly forbidden: " + tool_name
    if tool_name not in allowed:
        return False, "Tool not in allowed list: " + tool_name
    return True, "Tool permitted"


def check_action_permitted(agent_name, action):
    manifest = load_manifest(agent_name)
    if not manifest:
        return False, "No manifest found"
    forbidden = manifest.get("permissions", {}).get("forbidden_actions", [])
    for forbidden_action in forbidden:
        if any(word in action.lower() for word in forbidden_action.lower().split()):
            return False, "Action matches forbidden pattern: " + forbidden_action
    return True, "Action permitted"