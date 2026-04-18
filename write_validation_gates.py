import os

CONTENT = '''\
from __future__ import annotations
import re
from datetime import datetime
from typing import Any

VALID_DEPARTMENTS = {
    "engineering", "marketing", "sales", "operations",
    "research", "strategy", "finance", "customer_success", "general",
}

REQUIRED_SPEC_FIELDS = [
    "role_name", "department", "mission", "knowledge",
    "competencies", "skills", "experience", "decisions",
    "workflow", "tools", "quality", "boundaries",
]


# ── helpers ────────────────────────────────────────────────────────────────

def _str(agent: dict, key: str) -> str:
    """Return field as string, handling list or None."""
    val = agent.get(key) or agent.get("spec", {}).get(key, "")
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""


def _count_csv(text: str) -> int:
    """Count non-empty comma-separated items."""
    return sum(1 for item in text.split(",") if item.strip())


def _count_numbered_steps(text: str) -> int:
    """Count items that start with a digit followed by . or )."""
    return len(re.findall(r"(?:^|\\s)\\d+[.):]", text))


def _count_metrics(text: str) -> int:
    """Count numeric metrics (percentages, plain numbers, ranges)."""
    return len(re.findall(r"\\d+(?:\\.\\d+)?\\s*%|\\b\\d{2,}\\b", text))


def _count_sentences(text: str) -> int:
    """Count sentence-like segments split by . or newline."""
    parts = re.split(r"[.\\n]+", text)
    return sum(1 for p in parts if len(p.strip()) > 10)


# ── gate implementations ───────────────────────────────────────────────────

def _gate1_structural_integrity(agent: dict) -> dict:
    """Gate 1: All 12 required spec fields present and non-empty."""
    missing = []
    for field in REQUIRED_SPEC_FIELDS:
        val = _str(agent, field)
        if not val or val.strip() in ("", "none", "null"):
            missing.append(field)
    score = max(0, 10 - len(missing))
    passed = score >= 8
    details = (
        f"All 12 required fields present." if not missing
        else f"Missing or empty fields: {', '.join(missing)}."
    )
    recs = [f"Add '{f}' field to agent spec." for f in missing]
    return {
        "gate_number": 1, "name": "Structural Integrity",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": details, "recommendations": recs,
    }


def _gate2_role_clarity(agent: dict) -> dict:
    """Gate 2: Mission length and role_name specificity."""
    mission = _str(agent, "mission")
    role_name = _str(agent, "role_name").lower()
    score = 10
    recs = []
    details_parts = []

    if len(mission) < 100:
        score -= 5
        recs.append("Expand mission to at least 100 characters describing purpose and value.")
        details_parts.append(f"Mission too short ({len(mission)} chars, need 100+).")
    else:
        details_parts.append(f"Mission length OK ({len(mission)} chars).")

    generic_words = {"agent", "assistant", "helper", "bot", "ai"}
    role_words = set(role_name.split())
    if role_words and role_words.issubset(generic_words):
        score -= 3
        recs.append("Use a specific professional title for role_name (e.g. 'Sales Development Representative').")
        details_parts.append("role_name is too generic.")
    else:
        details_parts.append(f"role_name is specific: '{_str(agent, 'role_name')}'.")

    passed = score >= 7
    return {
        "gate_number": 2, "name": "Role Clarity",
        "score": float(max(0, score)), "max_score": 10, "passed": passed,
        "details": " ".join(details_parts), "recommendations": recs,
    }


def _gate3_knowledge_depth(agent: dict) -> dict:
    """Gate 3: At least 5 knowledge domains."""
    knowledge = _str(agent, "knowledge")
    count = _count_csv(knowledge)
    score = min(10, count * 2)
    passed = score >= 6
    recs = []
    if count < 5:
        recs.append(f"Add more knowledge domains (found {count}, need at least 5).")
    return {
        "gate_number": 3, "name": "Knowledge Depth",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found {count} knowledge domain(s) in knowledge field.",
        "recommendations": recs,
    }


def _gate4_skill_coverage(agent: dict) -> dict:
    """Gate 4: At least 5 specific skills."""
    skills = _str(agent, "skills")
    count = _count_csv(skills)
    score = min(10, count * 2)
    passed = score >= 6
    recs = []
    if count < 5:
        recs.append(f"Add more specific skills (found {count}, need at least 5).")
    return {
        "gate_number": 4, "name": "Skill Coverage",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found {count} skill(s) in skills field.",
        "recommendations": recs,
    }


def _gate5_decision_logic(agent: dict) -> dict:
    """Gate 5: IF/THEN decision rules present."""
    decisions = _str(agent, "decisions")
    if_count = len(re.findall(r"\\bIF\\b", decisions, re.IGNORECASE))
    then_count = len(re.findall(r"\\bTHEN\\b", decisions, re.IGNORECASE))
    rule_count = min(if_count, then_count)
    score = min(10, rule_count * 2)
    passed = score >= 6
    recs = []
    if rule_count < 3:
        recs.append(f"Add IF/THEN decision rules (found {rule_count}, need at least 3).")
        recs.append("Format: 'IF <condition> THEN <action>.'")
    return {
        "gate_number": 5, "name": "Decision Logic",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found {rule_count} IF/THEN decision rule(s).",
        "recommendations": recs,
    }


def _gate6_workflow_completeness(agent: dict) -> dict:
    """Gate 6: Numbered workflow steps."""
    workflow = _str(agent, "workflow")
    step_count = _count_numbered_steps(workflow)
    if step_count >= 8:
        score = 10
    elif step_count >= 6:
        score = 7
    elif step_count >= 4:
        score = 4
    else:
        score = 1
    passed = score >= 7
    recs = []
    if step_count < 8:
        recs.append(f"Expand workflow to 8 numbered steps (found {step_count}).")
        recs.append("Format: '1.action 2.action ... 8.action'")
    return {
        "gate_number": 6, "name": "Workflow Completeness",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found {step_count} numbered workflow step(s).",
        "recommendations": recs,
    }


def _gate7_tool_authorization(agent: dict) -> dict:
    """Gate 7: Specific tools listed."""
    tools = _str(agent, "tools")
    count = _count_csv(tools)
    score = min(10, count * 2)
    passed = score >= 4
    recs = []
    if count < 2:
        recs.append("List specific tools the agent uses (e.g. 'Salesforce, LinkedIn Sales Navigator, Outreach.io').")
    elif "various" in tools.lower() or "any tool" in tools.lower():
        recs.append("Replace generic tool references with specific named tools.")
    return {
        "gate_number": 7, "name": "Tool Authorization",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found {count} tool(s) listed.",
        "recommendations": recs,
    }


def _gate8_quality_standards(agent: dict) -> dict:
    """Gate 8: Measurable quality metrics with numbers/percentages."""
    quality = _str(agent, "quality")
    metric_count = _count_metrics(quality)
    if metric_count >= 3:
        score = 10
    elif metric_count == 2:
        score = 6
    elif metric_count == 1:
        score = 3
    else:
        score = 0
    passed = score >= 6
    recs = []
    if metric_count < 3:
        recs.append(f"Add measurable KPIs with numbers/percentages (found {metric_count}, need 3+).")
        recs.append("Example: 'Response rate above 8%. Meeting rate 15 per month. Show rate above 85%.'")
    return {
        "gate_number": 8, "name": "Quality Standards",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found {metric_count} measurable metric(s) in quality field.",
        "recommendations": recs,
    }


def _gate9_safety_boundaries(agent: dict) -> dict:
    """Gate 9: At least 3 specific prohibitions in boundaries."""
    boundaries = _str(agent, "boundaries")
    sentence_count = _count_sentences(boundaries)
    csv_count = _count_csv(boundaries)
    count = max(sentence_count, csv_count)
    score = min(10, count * 3)
    passed = score >= 6
    recs = []
    if count < 3:
        recs.append(f"Add more specific boundaries/prohibitions (found ~{count}, need at least 3).")
        recs.append("Example: 'Never misrepresent pricing. Never contact without consent. Never share PII.'")
    return {
        "gate_number": 9, "name": "Safety Boundaries",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": f"Found approximately {count} boundary statement(s).",
        "recommendations": recs,
    }


def _gate10_production_readiness(agent: dict) -> dict:
    """Gate 10: token_budget, department, and version set correctly."""
    score = 0
    recs = []
    details_parts = []

    # token_budget
    tb_raw = agent.get("token_budget") or agent.get("spec", {}).get("token_budget")
    try:
        tb = int(tb_raw)
        if 1000 <= tb <= 50000:
            score += 4
            details_parts.append(f"token_budget valid ({tb}).")
        else:
            recs.append(f"token_budget {tb} is outside recommended range 1000-50000.")
            details_parts.append(f"token_budget out of range ({tb}).")
    except (TypeError, ValueError):
        recs.append("Set a numeric token_budget between 1000 and 50000.")
        details_parts.append("token_budget missing or non-numeric.")

    # department
    dept = _str(agent, "department").lower().strip().replace(" ", "_").replace("-", "_")
    if dept in VALID_DEPARTMENTS:
        score += 3
        details_parts.append(f"department valid ('{dept}').")
    else:
        recs.append(f"Set department to one of: {', '.join(sorted(VALID_DEPARTMENTS))}.")
        details_parts.append(f"department '{dept}' not in valid list.")

    # version
    version = _str(agent, "version")
    if version and re.match(r"\\d+\\.\\d+", version):
        score += 3
        details_parts.append(f"version set ('{version}').")
    else:
        recs.append("Set version field (e.g. '1.0' or '1.0.0').")
        details_parts.append("version missing or malformed.")

    passed = score >= 7
    return {
        "gate_number": 10, "name": "Production Readiness",
        "score": float(score), "max_score": 10, "passed": passed,
        "details": " ".join(details_parts), "recommendations": recs,
    }


# ── public API ─────────────────────────────────────────────────────────────

_GATE_FUNCS = [
    _gate1_structural_integrity,
    _gate2_role_clarity,
    _gate3_knowledge_depth,
    _gate4_skill_coverage,
    _gate5_decision_logic,
    _gate6_workflow_completeness,
    _gate7_tool_authorization,
    _gate8_quality_standards,
    _gate9_safety_boundaries,
    _gate10_production_readiness,
]


def run_all_gates(agent: dict) -> dict:
    """Run all 10 validation gates against an agent spec and return full audit result."""
    # Flatten spec sub-dict into agent for easier field access
    flat = dict(agent)
    if "spec" in agent and isinstance(agent["spec"], dict):
        for k, v in agent["spec"].items():
            if k not in flat:
                flat[k] = v

    gates = [fn(flat) for fn in _GATE_FUNCS]
    total_score = sum(g["score"] for g in gates)
    overall = round(total_score / len(gates) * 10, 1)  # 0-100 scale
    passed_count = sum(1 for g in gates if g["passed"])
    failed_count = len(gates) - passed_count

    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 60:
        grade = "C"
    else:
        grade = "F"

    failed_names = [g["name"] for g in gates if not g["passed"]]
    if failed_count == 0:
        summary = f"Agent passes all 10 validation gates with a score of {overall}/100."
    else:
        summary = (
            f"Agent scores {overall}/100 (Grade {grade}). "
            f"{passed_count}/10 gates passed. "
            f"Failed: {', '.join(failed_names)}."
        )

    return {
        "agent_name": agent.get("name", agent.get("role_name", "Unknown")),
        "overall_score": overall,
        "grade": grade,
        "gates": gates,
        "passed_gates": passed_count,
        "failed_gates": failed_count,
        "summary": summary,
        "audited_at": datetime.utcnow().isoformat(),
    }


def get_gate_summary(agent: dict) -> dict:
    """Return a quick summary without full gate details."""
    result = run_all_gates(agent)
    return {
        "agent_name": result["agent_name"],
        "overall_score": result["overall_score"],
        "grade": result["grade"],
        "passed_gates": result["passed_gates"],
        "failed_gates": result["failed_gates"],
        "summary": result["summary"],
        "audited_at": result["audited_at"],
    }
'''

dest = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agents", "meta_agent", "validation_gates.py"
)
with open(dest, "w", encoding="utf-8") as f:
    f.write(CONTENT)
print(f"Written {len(CONTENT)} chars to {dest}")
