content = """
from datetime import datetime
from agents.meta_agent.manifest_manager import load_manifest

APPROVED_TOOLS = [
    "filesystem_server", "registry_server", "github_server",
    "web_search", "email", "calendar",
]

GOVERNANCE_RULES = [
    "cannot modify core", "cannot delete logs",
    "cannot create agents", "cannot modify config",
]


def gate_1_structural(agent_spec):
    errors = []
    required = ["agent_name", "version", "mission", "responsibilities",
                "non_responsibilities", "allowed_tools", "token_budget",
                "default_model", "escalation_triggers", "department"]
    for field in required:
        if not getattr(agent_spec, field, None):
            errors.append("Gate 1 — Missing: " + field)
    if len(agent_spec.responsibilities) < 3:
        errors.append("Gate 1 — Minimum 3 responsibilities required")
    if len(agent_spec.non_responsibilities) < 2:
        errors.append("Gate 1 — Minimum 2 non_responsibilities required")
    return len(errors) == 0, errors


def gate_2_role_definition(agent_spec):
    errors = []
    if len(agent_spec.mission) < 50:
        errors.append("Gate 2 — Mission too vague. Minimum 50 characters required.")
    if len(agent_spec.responsibilities) < 5:
        errors.append("Gate 2 — Minimum 5 responsibilities for clear role definition.")
    name = agent_spec.agent_name.lower()
    if name in ["agent", "my_agent", "test_agent", "new_agent"]:
        errors.append("Gate 2 — Agent name is too generic.")
    return len(errors) == 0, errors


def gate_3_skill_capability(agent_spec):
    errors = []
    has_skills = (
        getattr(agent_spec, "domain_knowledge", []) or
        getattr(agent_spec, "competencies", []) or
        getattr(agent_spec, "technical_skills", [])
    )
    if not has_skills:
        errors.append("Gate 3 — No skill definitions found. Agent needs domain knowledge, competencies, or technical skills.")
    return len(errors) == 0, errors


def gate_4_tool_authorization(agent_spec):
    errors = []
    for tool in agent_spec.allowed_tools:
        if tool not in APPROVED_TOOLS:
            errors.append("Gate 4 — Unauthorized tool: " + tool + ". Must be from approved list.")
    if not agent_spec.allowed_tools:
        errors.append("Gate 4 — No tools defined. Agent needs at least one tool.")
    return len(errors) == 0, errors


def gate_5_policy_governance(agent_spec):
    errors = []
    responsibilities_text = " ".join(agent_spec.responsibilities).lower()
    for rule in GOVERNANCE_RULES:
        keywords = rule.replace("cannot ", "").split()
        if all(kw in responsibilities_text for kw in keywords):
            errors.append("Gate 5 — Governance violation in responsibilities: " + rule)
    if agent_spec.token_budget > 20000:
        errors.append("Gate 5 — Token budget exceeds policy maximum of 20000.")
    return len(errors) == 0, errors


def gate_6_integration(agent_spec):
    errors = []
    name = agent_spec.agent_name
    if not name.replace("_", "").isalnum():
        errors.append("Gate 6 — Agent name must be snake_case alphanumeric only.")
    if len(name) > 60:
        errors.append("Gate 6 — Agent name too long. Maximum 60 characters.")
    if not agent_spec.default_model:
        errors.append("Gate 6 — No default model specified.")
    return len(errors) == 0, errors


def gate_7_testing(agent_spec):
    errors = []
    if len(agent_spec.responsibilities) < 3:
        errors.append("Gate 7 — Insufficient responsibilities for test coverage.")
    if not agent_spec.escalation_triggers:
        errors.append("Gate 7 — No escalation triggers defined. Agent cannot self-verify edge cases.")
    return len(errors) == 0, errors


def gate_8_resource(agent_spec):
    errors = []
    if agent_spec.token_budget < 1000:
        errors.append("Gate 8 — Token budget too low. Minimum 1000 tokens required.")
    if agent_spec.token_budget > 20000:
        errors.append("Gate 8 — Token budget exceeds maximum resource limit.")
    return len(errors) == 0, errors


def gate_9_security(agent_spec):
    errors = []
    dangerous_patterns = [
        "rm -rf", "delete all", "drop table", "system exec",
        "bypass security", "ignore safety", "override governance",
    ]
    all_text = (
        " ".join(agent_spec.responsibilities) + " " +
        " ".join(agent_spec.non_responsibilities) + " " +
        agent_spec.mission
    ).lower()
    for pattern in dangerous_patterns:
        if pattern in all_text:
            errors.append("Gate 9 — Dangerous pattern detected: " + pattern)
    return len(errors) == 0, errors


def gate_10_simulation(agent_spec):
    errors = []
    score = 0
    if len(agent_spec.responsibilities) >= 5: score += 2
    if len(agent_spec.non_responsibilities) >= 3: score += 2
    if len(agent_spec.escalation_triggers) >= 3: score += 2
    if len(agent_spec.mission) >= 100: score += 2
    if agent_spec.allowed_tools: score += 1
    if agent_spec.token_budget >= 5000: score += 1
    if score < 7:
        errors.append("Gate 10 — Simulation score too low: " + str(score) + "/10. Agent needs more definition.")
    return len(errors) == 0, errors


GATES = [
    ("Gate 1 — Structural Integrity", gate_1_structural),
    ("Gate 2 — Role Definition", gate_2_role_definition),
    ("Gate 3 — Skill Capability", gate_3_skill_capability),
    ("Gate 4 — Tool Authorization", gate_4_tool_authorization),
    ("Gate 5 — Policy Governance", gate_5_policy_governance),
    ("Gate 6 — Integration", gate_6_integration),
    ("Gate 7 — Testing", gate_7_testing),
    ("Gate 8 — Resource", gate_8_resource),
    ("Gate 9 — Security", gate_9_security),
    ("Gate 10 — Simulation", gate_10_simulation),
]


def run_all_validation_gates(agent_spec):
    all_errors = []
    gate_results = []
    for gate_name, gate_fn in GATES:
        passed, errors = gate_fn(agent_spec)
        gate_results.append({"gate": gate_name, "passed": passed, "errors": errors})
        if not passed:
            all_errors.extend(errors)
    gates_passed = sum(1 for g in gate_results if g["passed"])
    return {
        "passed": len(all_errors) == 0,
        "gates_passed": gates_passed,
        "total_gates": len(GATES),
        "errors": all_errors,
        "gate_results": gate_results,
        "timestamp": datetime.utcnow().isoformat(),
    }
"""

with open("agents/meta_agent/validation_gates.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("validation_gates.py created with all 10 gates")
