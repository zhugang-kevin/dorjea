from __future__ import annotations
import re
from typing import Any

VALID_DEPARTMENTS = [
    "sales", "marketing", "research", "operations", "engineering",
    "strategy", "finance", "customer_success", "general",
]

_HUMAN_WORDS = {"human", "person", "man", "woman", "employee", "staff", "worker", "individual"}


def _str(agent: dict, key: str) -> str:
    val = agent.get(key) or agent.get("spec", {}).get(key, "")
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val).strip() if val else ""


def _count_csv(text: str) -> int:
    return sum(1 for item in text.split(",") if item.strip())


def _count_if(text: str) -> int:
    return len(re.findall(r"\bIF\b", text, re.IGNORECASE))


def _count_steps(text: str) -> int:
    return len(re.findall(r"(?:^|\s)\d+[.):]", text))


def _fail(code: int, message: str) -> dict:
    return {"invariant": code, "passed": False, "message": message}


def _pass(code: int, message: str) -> dict:
    return {"invariant": code, "passed": True, "message": message}


# ── invariant checks ───────────────────────────────────────────────────────

def _i1(agent: dict, existing: list) -> dict:
    name = _str(agent, "name") or _str(agent, "role_name")
    dupes = [a for a in existing if (_str(a, "name") or _str(a, "role_name")).lower() == name.lower()]
    if dupes:
        return _fail(1, f"Duplicate agent name '{name}' — an active agent with this name already exists.")
    return _pass(1, "Agent name is unique.")


def _i2(agent: dict, existing: list) -> dict:
    dept = _str(agent, "department").lower().replace(" ", "_").replace("-", "_")
    if dept not in VALID_DEPARTMENTS:
        return _fail(2, f"Department '{dept}' is not in the approved list: {', '.join(VALID_DEPARTMENTS)}.")
    return _pass(2, f"Department '{dept}' is valid.")


def _i3(agent: dict, existing: list) -> dict:
    version = _str(agent, "version")
    if not version or not re.match(r"^\d+\.\d+", version):
        return _fail(3, f"Version '{version}' must be in X.Y format (e.g. '1.0').")
    return _pass(3, f"Version '{version}' is valid.")


def _i4(agent: dict, existing: list) -> dict:
    mission = _str(agent, "mission")
    if len(mission) < 50:
        return _fail(4, f"Mission is {len(mission)} chars — minimum is 50.")
    return _pass(4, f"Mission length OK ({len(mission)} chars).")


def _i5(agent: dict, existing: list) -> dict:
    role = _str(agent, "role_name")
    if len(role) < 3:
        return _fail(5, f"role_name '{role}' is too short — minimum 3 characters.")
    if len(role) > 100:
        return _fail(5, f"role_name is {len(role)} chars — maximum is 100.")
    return _pass(5, f"role_name length OK ({len(role)} chars).")


def _i6(agent: dict, existing: list) -> dict:
    knowledge = _str(agent, "knowledge") or _str(agent, "knowledge_domains")
    count = _count_csv(knowledge)
    if count < 3:
        return _fail(6, f"Found {count} knowledge domain(s) — minimum is 3.")
    return _pass(6, f"Knowledge domains OK ({count} found).")


def _i7(agent: dict, existing: list) -> dict:
    comp = _str(agent, "competencies")
    count = _count_csv(comp)
    if count < 3:
        return _fail(7, f"Found {count} competenc(y/ies) — minimum is 3.")
    return _pass(7, f"Competencies OK ({count} found).")


def _i8(agent: dict, existing: list) -> dict:
    skills = _str(agent, "skills") or _str(agent, "technical_skills")
    count = _count_csv(skills)
    if count < 3:
        return _fail(8, f"Found {count} skill(s) — minimum is 3.")
    return _pass(8, f"Skills OK ({count} found).")


def _i9(agent: dict, existing: list) -> dict:
    exp = _str(agent, "experience") or _str(agent, "experience_patterns")
    if len(exp) < 50:
        return _fail(9, f"Experience field is {len(exp)} chars — minimum is 50.")
    return _pass(9, f"Experience length OK ({len(exp)} chars).")


def _i10(agent: dict, existing: list) -> dict:
    knowledge = set(w.lower() for w in re.split(r"[,\s]+", _str(agent, "knowledge") or _str(agent, "knowledge_domains")) if w)
    competencies = set(w.lower() for w in re.split(r"[,\s]+", _str(agent, "competencies")) if w)
    overlap = knowledge & competencies
    if len(overlap) > 3:
        return _fail(10, f"Knowledge and competencies share too many identical words: {', '.join(sorted(overlap)[:5])}.")
    return _pass(10, "Knowledge and competencies are sufficiently distinct.")


def _i11(agent: dict, existing: list) -> dict:
    decisions = _str(agent, "decisions") or _str(agent, "decision_rules")
    count = _count_if(decisions)
    if count < 2:
        return _fail(11, f"Found {count} IF condition(s) in decisions — minimum is 2.")
    return _pass(11, f"Decision IF conditions OK ({count} found).")


def _i12(agent: dict, existing: list) -> dict:
    workflow = _str(agent, "workflow") or _str(agent, "execution_workflow")
    count = _count_steps(workflow)
    if count < 4:
        return _fail(12, f"Found {count} workflow step(s) — minimum is 4.")
    return _pass(12, f"Workflow steps OK ({count} found).")


def _i13(agent: dict, existing: list) -> dict:
    tools = _str(agent, "tools") or _str(agent, "tool_access")
    if not tools.strip() or tools.strip().lower() in ("none", "null", ""):
        return _fail(13, "No tools specified — agent must have at least 1 tool.")
    return _pass(13, f"Tools specified: '{tools[:60]}'.")


def _i14(agent: dict, existing: list) -> dict:
    quality = _str(agent, "quality") or _str(agent, "quality_standards") or _str(agent, "success_metrics")
    count = _count_csv(quality)
    if count < 2:
        parts = [p.strip() for p in re.split(r"[.\n]", quality) if len(p.strip()) > 5]
        count = len(parts)
    if count < 2:
        return _fail(14, f"Found {count} quality standard(s) — minimum is 2.")
    return _pass(14, f"Quality standards OK ({count} found).")


def _i15(agent: dict, existing: list) -> dict:
    boundaries = _str(agent, "boundaries")
    count = _count_csv(boundaries)
    if count < 2:
        parts = [p.strip() for p in re.split(r"[.\n]", boundaries) if len(p.strip()) > 5]
        count = len(parts)
    if count < 2:
        return _fail(15, f"Found {count} boundary statement(s) — minimum is 2.")
    return _pass(15, f"Boundaries OK ({count} found).")


def _i16(agent: dict, existing: list) -> dict:
    boundaries = _str(agent, "boundaries")
    if not boundaries.strip():
        return _fail(16, "Boundaries field is empty — this is a required safety field.")
    return _pass(16, "Boundaries field is populated.")


def _i17(agent: dict, existing: list) -> dict:
    raw = agent.get("token_budget") or agent.get("spec", {}).get("token_budget")
    try:
        tb = int(raw)
    except (TypeError, ValueError):
        return _fail(17, f"token_budget '{raw}' is not a valid integer.")
    if not (500 <= tb <= 100000):
        return _fail(17, f"token_budget {tb} is outside allowed range 500–100000.")
    return _pass(17, f"token_budget {tb} is within range.")


def _i18(agent: dict, existing: list) -> dict:
    role = _str(agent, "role_name").lower()
    mission = _str(agent, "mission").lower()
    combined = role + " " + mission
    words = set(re.findall(r"\b\w+\b", combined))
    found = words & _HUMAN_WORDS
    if found:
        return _fail(18, f"Agent role/mission contains human identity words: {', '.join(found)}. Agents must not claim to be human.")
    return _pass(18, "No human identity claims detected.")


def _i19(agent: dict, existing: list) -> dict:
    boundaries = _str(agent, "boundaries").lower()
    if "never" not in boundaries:
        return _fail(19, "Boundaries must include at least one 'never' statement (e.g. 'Never share PII').")
    return _pass(19, "Boundaries contain at least one 'never' statement.")


def _i20(agent: dict, existing: list) -> dict:
    quality = _str(agent, "quality") or _str(agent, "quality_standards") or _str(agent, "success_metrics")
    if not quality.strip():
        return _fail(20, "Quality field is empty — measurable standards are required.")
    return _pass(20, "Quality field is populated.")


def _i21(agent: dict, existing: list) -> dict:
    dept = _str(agent, "department").lower().replace(" ", "_").replace("-", "_")
    if dept not in VALID_DEPARTMENTS:
        return _fail(21, f"Department '{dept}' not in approved list: {', '.join(VALID_DEPARTMENTS)}.")
    return _pass(21, f"Department '{dept}' is approved.")


def _i22(agent: dict, existing: list) -> dict:
    workflow = _str(agent, "workflow") or _str(agent, "execution_workflow")
    steps = re.findall(r"(?:^|\s)(\d+)[.):]", workflow)
    if len(steps) >= 2:
        nums = [int(s) for s in steps]
        for i in range(1, len(nums)):
            if nums[i] != nums[i - 1] + 1:
                return _fail(22, f"Workflow steps are not in sequential order: found {nums}.")
    return _pass(22, "Workflow steps are in numbered sequence.")


def _i23(agent: dict, existing: list) -> dict:
    decisions = (_str(agent, "decisions") or _str(agent, "decision_rules")).strip().lower()
    experience = (_str(agent, "experience") or _str(agent, "experience_patterns")).strip().lower()
    if decisions and experience and decisions == experience:
        return _fail(23, "Decisions field is identical to experience field — they must be distinct.")
    return _pass(23, "Decisions and experience fields are distinct.")


def _i24(agent: dict, existing: list) -> dict:
    raw = agent.get("token_budget") or agent.get("spec", {}).get("token_budget")
    if isinstance(raw, str):
        return _fail(24, f"token_budget must be an integer, not a string (got '{raw}').")
    if not isinstance(raw, int):
        return _fail(24, f"token_budget must be an integer (got {type(raw).__name__}).")
    return _pass(24, "token_budget is an integer.")


def _i25(agent: dict, existing: list) -> dict:
    name = _str(agent, "name") or _str(agent, "role_name")
    if not re.match(r"^[A-Za-z0-9 _\-]+$", name):
        bad = re.findall(r"[^A-Za-z0-9 _\-]", name)
        return _fail(25, f"Agent name contains invalid characters: {bad}. Only letters, digits, spaces, hyphens, and underscores are allowed.")
    return _pass(25, "Agent name contains only valid characters.")


# ── public API ─────────────────────────────────────────────────────────────

_CHECKS = [
    _i1, _i2, _i3, _i4, _i5,
    _i6, _i7, _i8, _i9, _i10,
    _i11, _i12, _i13, _i14, _i15,
    _i16, _i17, _i18, _i19, _i20,
    _i21, _i22, _i23, _i24, _i25,
]


def check_invariants(agent: dict, existing_agents: list = []) -> dict:
    """Run all 25 architecture invariants against an agent dict.

    Returns a dict with keys:
      passed        bool   — True only if all invariants pass
      violations    list   — invariant results that failed
      results       list   — all 25 invariant results
      passed_count  int
      failed_count  int
      summary       str
    """
    results = [fn(agent, existing_agents) for fn in _CHECKS]
    violations = [r for r in results if not r["passed"]]
    passed_count = len(results) - len(violations)

    if not violations:
        summary = f"All 25 architecture invariants passed."
    else:
        codes = ", ".join(str(v["invariant"]) for v in violations)
        summary = (
            f"{passed_count}/25 invariants passed. "
            f"Violations on invariant(s): {codes}."
        )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "results": results,
        "passed_count": passed_count,
        "failed_count": len(violations),
        "summary": summary,
    }


_INVARIANT_DESCRIPTIONS = [
    (1,  "identity",    "Agent must have a unique name — no two active agents can share an identical name."),
    (2,  "identity",    "Agent must have a valid department from the approved list."),
    (3,  "identity",    "Agent must have a version number in X.Y format."),
    (4,  "identity",    "Agent mission must be at least 50 characters."),
    (5,  "identity",    "Agent role_name must be 3–100 characters."),
    (6,  "knowledge",   "Agent must have at least 3 knowledge domains."),
    (7,  "knowledge",   "Agent must have at least 3 competencies."),
    (8,  "knowledge",   "Agent must have at least 3 skills."),
    (9,  "knowledge",   "Agent experience field must be at least 50 characters."),
    (10, "knowledge",   "Agent knowledge must not duplicate competencies word-for-word."),
    (11, "decision",    "Agent decisions must contain at least 2 IF conditions."),
    (12, "decision",    "Agent workflow must have at least 4 steps."),
    (13, "decision",    "Agent must have at least 1 tool specified."),
    (14, "decision",    "Agent must have at least 2 quality standards."),
    (15, "decision",    "Agent must have at least 2 boundaries defined."),
    (16, "safety",      "Agent must never have an empty boundaries field."),
    (17, "safety",      "Agent token_budget must be between 500 and 100000."),
    (18, "safety",      "Agent must not claim to be human in its role definition."),
    (19, "safety",      "Agent boundaries must include at least one 'never' statement."),
    (20, "safety",      "Agent quality field must not be empty."),
    (21, "operational", "Agent department must match one of the 9 approved values."),
    (22, "operational", "Agent workflow steps must be in numbered sequence."),
    (23, "operational", "Agent decisions field must not be identical to experience field."),
    (24, "operational", "Agent token_budget must be an integer, not a string."),
    (25, "operational", "Agent name must not contain special characters except hyphen and underscore."),
]


def get_invariant_list() -> list[dict]:
    """Return all 25 invariants as a list of dicts with number, category, description."""
    return [
        {"number": n, "category": cat, "description": desc}
        for n, cat, desc in _INVARIANT_DESCRIPTIONS
    ]
