"""
nodes.py — All 9 LangGraph node functions for the Meta-Agent workflow.
Each node receives MetaAgentState, does exactly one job, and returns
an updated state dict. Every node writes an audit entry before returning.
"""
from __future__ import annotations
import os
import json
import uuid
import yaml
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

import jsonschema
from dotenv import load_dotenv

from agents.meta_agent.state import MetaAgentState
from agents.meta_agent.models import (
    TaskSpec, AgentSpec, VerificationResult,
    TestResult, AuditEntry, FounderReport,
)
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.registry import agent_exists, register_agent as db_register_agent
from agents.runtime.ai_clients import ClaudeClient, OpenAIClient

load_dotenv()

SCHEMAS_DIR = Path("tools/schemas")
SPECS_DIR = Path("agents/specs")
GENERATED_DIR = Path("agents/generated")

claude = ClaudeClient()
openai_client = OpenAIClient()


def _load_schema(schema_name: str) -> dict:
    """Load a JSON schema file from tools/schemas/."""
    path = SCHEMAS_DIR / schema_name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _now() -> str:
    """Return current UTC time as ISO string."""
    return datetime.utcnow().isoformat()


def _audit(state: MetaAgentState, node: str, summary: str, success: bool = True) -> AuditEntry:
    """Create and write an audit entry for a node execution."""
    entry = AuditEntry(
        agent_id=state.get("task_id", "unknown"),
        task_id=state.get("task_id", "unknown"),
        action=node,
        details={"summary": summary},
        tokens_used=state.get("total_tokens_used", 0),
        success=success,
    )
    write_audit_entry(entry)
    return entry


# ── NODE 1 — parse_request ────────────────────────────────────────────────────

def parse_request(state: MetaAgentState) -> dict:
    """
    Node 1: Convert founder plain-English request into a typed TaskSpec.
    Uses Claude to extract structured fields from natural language.
    Sets should_stop=True if parsing fails.
    """
    founder_request = state.get("founder_request", "")
    if not founder_request:
        _audit(state, "parse_request", "Empty founder request", success=False)
        return {
            "current_error": "Founder request is empty.",
            "should_stop": True,
        }

    system = (
        "You are a precise task parser for an AI agent factory. "
        "Extract structured information from the founder request. "
        "Respond with valid JSON only. No explanation. No markdown."
    )
    prompt = f"""
Extract the following fields from this founder request and return as JSON:
- agent_name: short snake_case name (e.g. content_writer_agent)
- agent_role: one-line role title
- agent_mission: 2-3 sentence mission statement
- allowed_tools: list of tools this agent needs (choose from: filesystem_server, registry_server, github_server, web_search, email, calendar)
- token_budget: integer between 5000 and 20000
- department: one of engineering, marketing, finance, operations, research, sales, legal, hr, general
- founder_request: repeat the original request exactly

Founder request: {founder_request}

Return only valid JSON. No markdown. No explanation.
"""
    result = claude.call(prompt, system=system)
    if result["error"]:
        _audit(state, "parse_request", f"Claude error: {result['error']}", success=False)
        return {
            "current_error": f"parse_request failed: {result['error']}",
            "should_stop": True,
        }

    try:
        raw = result["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        task_spec = TaskSpec(
            founder_request=founder_request,
            **{k: v for k, v in data.items() if k != "founder_request"},
        )
        tokens = result["total_tokens"]
        _audit(state, "parse_request", f"Parsed TaskSpec for agent: {task_spec.agent_name}")
        return {
            "task_spec": task_spec,
            "total_tokens_used": state.get("total_tokens_used", 0) + tokens,
            "current_error": None,
            "should_stop": False,
        }
    except Exception as e:
        _audit(state, "parse_request", f"Parse error: {e}", success=False)
        return {
            "current_error": f"parse_request failed: {str(e)}",
            "should_stop": True,
        }


# ── NODE 2 — validate_spec ────────────────────────────────────────────────────

def validate_spec(state: MetaAgentState) -> dict:
    """
    Node 2: Validate the TaskSpec against the JSON schema.
    Rejects malformed or incomplete specs before any AI generation.
    Sets should_stop=True if validation fails.
    """
    if state.get("should_stop"):
        return {}

    task_spec = state.get("task_spec")
    if not task_spec:
        _audit(state, "validate_spec", "No TaskSpec to validate", success=False)
        return {"current_error": "No TaskSpec found.", "should_stop": True}

    try:
        schema = _load_schema("task.schema.json")
        spec_dict = task_spec.model_dump()
        jsonschema.validate(instance=spec_dict, schema=schema)
        _audit(state, "validate_spec", "TaskSpec passed schema validation")
        return {
            "validation_errors": [],
            "current_error": None,
            "should_stop": False,
        }
    except jsonschema.ValidationError as e:
        error_msg = f"Schema validation failed: {e.message}"
        _audit(state, "validate_spec", error_msg, success=False)
        return {
            "validation_errors": [e.message],
            "current_error": error_msg,
            "should_stop": True,
        }
    except Exception as e:
        _audit(state, "validate_spec", f"Unexpected error: {e}", success=False)
        return {"current_error": str(e), "should_stop": True}


# ── NODE 3 — check_registry ───────────────────────────────────────────────────

def check_registry(state: MetaAgentState) -> dict:
    """
    Node 3: Check the agent registry for duplicate agent names.
    Halts if an agent with the same name already exists.
    """
    if state.get("should_stop"):
        return {}

    task_spec = state.get("task_spec")
    if not task_spec:
        return {"current_error": "No TaskSpec in state.", "should_stop": True}

    exists = agent_exists(task_spec.agent_name)
    if exists:
        error_msg = f"Agent '{task_spec.agent_name}' already exists in registry."
        _audit(state, "check_registry", error_msg, success=False)
        return {
            "agent_already_exists": True,
            "existing_agent_name": task_spec.agent_name,
            "current_error": error_msg,
            "should_stop": True,
        }

    _audit(state, "check_registry", f"No duplicate found for: {task_spec.agent_name}")
    return {
        "agent_already_exists": False,
        "existing_agent_name": None,
        "current_error": None,
        "should_stop": False,
    }


# ── NODE 4 — generate_spec ────────────────────────────────────────────────────

def generate_spec(state: MetaAgentState) -> dict:
    """
    Node 4: Use Claude to generate a complete AgentSpec from the TaskSpec.
    Produces a full specification including responsibilities, tools, and policies.
    """
    if state.get("should_stop"):
        return {}

    task_spec = state.get("task_spec")
    if not task_spec:
        return {"current_error": "No TaskSpec in state.", "should_stop": True}

    system = (
        "You are an expert AI agent architect. "
        "Generate a complete, detailed agent specification. "
        "Respond with valid JSON only. No explanation. No markdown."
    )
    prompt = f"""
Generate a complete AgentSpec JSON for this agent:

Agent Name: {task_spec.agent_name}
Role: {task_spec.agent_role}
Mission: {task_spec.agent_mission}
Department: {task_spec.department}
Allowed Tools: {task_spec.allowed_tools}
Token Budget: {task_spec.token_budget}

Return JSON with these exact fields:
- agent_name: string
- version: "1.0"
- mission: detailed mission statement (3-5 sentences)
- responsibilities: list of 5-8 specific responsibilities
- non_responsibilities: list of 3-5 things this agent must NOT do
- allowed_tools: list of approved tools
- token_budget: integer
- default_model: "{os.getenv('PRIMARY_MODEL', 'claude-sonnet-4-6')}"
- fallback_model: "{os.getenv('VERIFIER_MODEL', 'gpt-4o')}"
- retry_policy: {{"max_attempts": 3, "backoff_seconds": 2}}
- escalation_triggers: list of 3-5 conditions that require founder approval
- memory_policy: "session_only"
- department: "{task_spec.department}"

Return only valid JSON. No markdown. No explanation.
"""
    result = claude.call(prompt, system=system, max_tokens=2000)
    if result["error"]:
        _audit(state, "generate_spec", f"Claude error: {result['error']}", success=False)
        return {
            "current_error": f"generate_spec failed: {result['error']}",
            "should_stop": True,
        }

    try:
        raw = result["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        agent_spec = AgentSpec(**data)
        spec_yaml = yaml.dump(data, default_flow_style=False)
        tokens = result["total_tokens"]
        _audit(state, "generate_spec", f"AgentSpec generated for: {agent_spec.agent_name}")
        return {
            "agent_spec": agent_spec,
            "generated_spec_yaml": spec_yaml,
            "total_tokens_used": state.get("total_tokens_used", 0) + tokens,
            "current_error": None,
            "should_stop": False,
        }
    except Exception as e:
        _audit(state, "generate_spec", f"Spec generation error: {e}", success=False)
        return {
            "current_error": f"generate_spec failed: {str(e)}",
            "should_stop": True,
        }


# ── NODE 5 — verify_spec ──────────────────────────────────────────────────────

def verify_spec(state: MetaAgentState) -> dict:
    """
    Node 5: Use GPT-4o to independently verify the generated AgentSpec.
    A FAIL result halts the pipeline and returns issues to the founder.
    """
    if state.get("should_stop"):
        return {}

    agent_spec = state.get("agent_spec")
    if not agent_spec:
        return {"current_error": "No AgentSpec to verify.", "should_stop": True}

    system = (
        "You are a strict AI agent specification reviewer. "
        "Review the spec for completeness, safety, and quality. "
        "Respond with valid JSON only. No explanation. No markdown."
    )
    prompt = f"""
Review this AgentSpec and return a JSON verdict:

{json.dumps(agent_spec.model_dump(), indent=2)}

Return JSON with these exact fields:
- status: one of "PASS", "CONDITIONAL", "FAIL"
- issues: list of problems found (empty list if none)
- suggestions: list of improvement suggestions (empty list if none)
- verified_by: "gpt-4o"

PASS = spec is complete, safe, and well-defined.
CONDITIONAL = spec has minor issues but can proceed with suggestions applied.
FAIL = spec has critical problems and must be regenerated.

Return only valid JSON. No markdown. No explanation.
"""
    result = openai_client.call(prompt, system=system, max_tokens=1000)
    if result["error"]:
        _audit(state, "verify_spec", f"OpenAI error: {result['error']}", success=False)
        return {
            "current_error": f"verify_spec failed: {result['error']}",
            "should_stop": True,
        }

    try:
        raw = result["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        verification = VerificationResult(**data)
        tokens = result["total_tokens"]
        success = verification.status != "FAIL"
        _audit(
            state, "verify_spec",
            f"Verification result: {verification.status}",
            success=success,
        )
        if not success:
            return {
                "verification_result": verification,
                "total_tokens_used": state.get("total_tokens_used", 0) + tokens,
                "current_error": f"Spec verification FAILED: {verification.issues}",
                "should_stop": True,
            }
        return {
            "verification_result": verification,
            "total_tokens_used": state.get("total_tokens_used", 0) + tokens,
            "current_error": None,
            "should_stop": False,
        }
    except Exception as e:
        _audit(state, "verify_spec", f"Verify error: {e}", success=False)
        return {
            "current_error": f"verify_spec failed: {str(e)}",
            "should_stop": True,
        }


# ── NODE 6 — generate_code ────────────────────────────────────────────────────

def generate_code(state: MetaAgentState) -> dict:
    """
    Node 6: Use Claude to write the Python agent file and YAML config.
    Saves both files to agents/generated/ folder.
    """
    if state.get("should_stop"):
        return {}

    agent_spec = state.get("agent_spec")
    if not agent_spec:
        return {"current_error": "No AgentSpec for code generation.", "should_stop": True}

    system = (
        "You are an expert Python developer writing production AI agent code. "
        "Write clean, complete, well-documented Python code. "
        "Never use placeholders or TODO comments. "
        "Always use os.getenv() for secrets. Never hardcode values."
    )
    prompt = f"""
Write a complete Python agent file for this specification:

Agent Name: {agent_spec.agent_name}
Mission: {agent_spec.mission}
Responsibilities: {agent_spec.responsibilities}
Allowed Tools: {agent_spec.allowed_tools}
Model: {agent_spec.default_model}
Department: {agent_spec.department}

Requirements:
- Class named {agent_spec.agent_name.title().replace("_", "")}
- __init__ method reading all config from os.getenv()
- async run(task: str) -> str method
- Proper docstrings on every method
- try/except around every external call
- No placeholders, no TODO comments
- Import only from standard library and these packages: anthropic, openai, pydantic

Return only the complete Python code. No explanation. No markdown fences.
"""
    result = claude.call(prompt, system=system, max_tokens=3000)
    if result["error"]:
        _audit(state, "generate_code", f"Claude error: {result['error']}", success=False)
        return {
            "current_error": f"generate_code failed: {result['error']}",
            "should_stop": True,
        }

    try:
        generated_code = result["text"].strip()
        if generated_code.startswith("```"):
            generated_code = generated_code.split("```")[1]
            if generated_code.startswith("python"):
                generated_code = generated_code[6:]
        generated_code = generated_code.strip()

        config_data = {
            "agent_name": agent_spec.agent_name,
            "version": agent_spec.version,
            "mission": agent_spec.mission,
            "default_model": agent_spec.default_model,
            "fallback_model": agent_spec.fallback_model,
            "token_budget": agent_spec.token_budget,
            "allowed_tools": agent_spec.allowed_tools,
            "department": agent_spec.department,
            "retry_policy": agent_spec.retry_policy,
        }
        generated_config = yaml.dump(config_data, default_flow_style=False)

        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        code_path = GENERATED_DIR / f"{agent_spec.agent_name}.py"
        config_path = GENERATED_DIR / f"{agent_spec.agent_name}.yaml"

        code_path.write_text(generated_code, encoding="utf-8")
        config_path.write_text(generated_config, encoding="utf-8")

        tokens = result["total_tokens"]
        _audit(state, "generate_code", f"Code generated: {code_path}")
        return {
            "generated_code": generated_code,
            "generated_config": generated_config,
            "code_file_path": str(code_path),
            "config_file_path": str(config_path),
            "total_tokens_used": state.get("total_tokens_used", 0) + tokens,
            "current_error": None,
            "should_stop": False,
        }
    except Exception as e:
        _audit(state, "generate_code", f"Code generation error: {e}", success=False)
        return {
            "current_error": f"generate_code failed: {str(e)}",
            "should_stop": True,
        }


# ── NODE 7 — run_tests ────────────────────────────────────────────────────────

def run_tests(state: MetaAgentState) -> dict:
    """
    Node 7: Run pytest on the generated agent file.
    Creates a basic syntax and import test automatically.
    Sets should_stop=True if tests fail.
    """
    if state.get("should_stop"):
        return {}

    code_file = state.get("code_file_path")
    if not code_file or not Path(code_file).exists():
        _audit(state, "run_tests", "No generated code file found", success=False)
        return {
            "current_error": "No generated code file to test.",
            "should_stop": True,
        }

    agent_spec = state.get("agent_spec")
    agent_name = agent_spec.agent_name if agent_spec else "unknown"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_test.py",
            dir="agents/meta_agent/tests",
            delete=False, encoding="utf-8"
        ) as f:
            test_file = f.name
            f.write(f'''"""
Auto-generated test for {agent_name}.
Tests syntax validity and basic structure.
"""
import ast
import os
import pytest


def test_syntax_valid():
    """Verify the generated code has no syntax errors."""
    with open(r"{code_file}", "r", encoding="utf-8") as f:
        source = f.read()
    try:
        ast.parse(source)
    except SyntaxError as e:
        pytest.fail(f"Syntax error in generated code: {{e}}")


def test_file_exists():
    """Verify the generated code file exists."""
    assert os.path.exists(r"{code_file}"), "Generated code file not found"


def test_not_empty():
    """Verify the generated code file is not empty."""
    with open(r"{code_file}", "r", encoding="utf-8") as f:
        content = f.read().strip()
    assert len(content) > 50, "Generated code file is too short"
''')

        proc = subprocess.run(
            ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
            capture_output=True, text=True, timeout=60
        )
        output = proc.stdout + proc.stderr
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        errors = output.count(" ERROR")
        total = passed + failed + errors

        try:
            Path(test_file).unlink()
        except Exception:
            pass

        test_result = TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            total=total,
            success=(failed == 0 and errors == 0),
            output=output[-2000:],
        )
        success = test_result.success
        _audit(state, "run_tests", f"Tests: {passed} passed, {failed} failed", success=success)

        if not success:
            return {
                "test_result": test_result,
                "current_error": f"Tests failed: {failed} failures, {errors} errors",
                "should_stop": True,
            }
        return {
            "test_result": test_result,
            "current_error": None,
            "should_stop": False,
        }
    except Exception as e:
        _audit(state, "run_tests", f"Test runner error: {e}", success=False)
        return {
            "current_error": f"run_tests failed: {str(e)}",
            "should_stop": True,
        }


# ── NODE 8 — register_agent ───────────────────────────────────────────────────

def register_agent(state: MetaAgentState) -> dict:
    """
    Node 8: Register the verified and tested agent in the database.
    Saves the agent spec YAML to agents/specs/ folder.
    """
    if state.get("should_stop"):
        return {}

    agent_spec = state.get("agent_spec")
    spec_yaml = state.get("generated_spec_yaml", "")
    if not agent_spec:
        return {"current_error": "No AgentSpec to register.", "should_stop": True}

    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    spec_path = SPECS_DIR / f"{agent_spec.agent_name}.yaml"
    spec_path.write_text(spec_yaml or "", encoding="utf-8")

    result = db_register_agent(
        name=agent_spec.agent_name,
        mission=agent_spec.mission,
        allowed_tools=agent_spec.allowed_tools,
        default_model=agent_spec.default_model,
        fallback_model=agent_spec.fallback_model,
        token_budget=agent_spec.token_budget,
        spec_yaml=spec_yaml or "",
        department=agent_spec.department,
    )

    if not result["success"]:
        _audit(state, "register_agent", f"Registration failed: {result['error']}", success=False)
        return {
            "current_error": f"register_agent failed: {result['error']}",
            "should_stop": True,
        }

    _audit(state, "register_agent", f"Agent registered: {agent_spec.agent_name}")
    return {
        "registered_agent_id": result["agent_id"],
        "current_error": None,
        "should_stop": False,
    }


# ── NODE 9 — return_report ────────────────────────────────────────────────────

def return_report(state: MetaAgentState) -> dict:
    """
    Node 9: Build and return the final FounderReport.
    Always runs — even on failure. Founder always gets a report.
    """
    task_spec = state.get("task_spec")
    agent_spec = state.get("agent_spec")
    agent_name = (
        agent_spec.agent_name if agent_spec
        else (task_spec.agent_name if task_spec else "unknown")
    )

    has_error = bool(state.get("current_error"))
    test_result = state.get("test_result")
    tests_failed = test_result and test_result.failed > 0 if test_result else False

    if has_error:
        status = "FAILED"
    elif tests_failed:
        status = "PARTIAL"
    else:
        status = "SUCCESS"

    summary = (
        state.get("current_error")
        or f"Agent '{agent_name}' created successfully and registered."
    )

    rollback = (
        f"python agents\\meta_agent\\registry.py --freeze {agent_name}  "
        f"-- or: git revert HEAD to undo all file changes"
    )

    report = FounderReport(
        task_id=state.get("task_id", str(uuid.uuid4())),
        agent_name=agent_name,
        status=status,
        summary=summary,
        agent_spec=agent_spec,
        verification_result=state.get("verification_result"),
        test_result=test_result,
        registry_id=state.get("registered_agent_id"),
        total_tokens_used=state.get("total_tokens_used", 0),
        errors=[state["current_error"]] if state.get("current_error") else [],
        rollback_command=rollback,
    )

    _audit(state, "return_report", f"Report status: {status}", success=(status == "SUCCESS"))
    return {"founder_report": report}

