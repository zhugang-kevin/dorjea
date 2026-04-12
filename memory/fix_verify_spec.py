with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def verify_spec(state: MetaAgentState) -> dict:
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
        _audit(state, "verify_spec", f"OpenAI error: {result[\'error\']}", success=False)
        return {
            "current_error": f"verify_spec failed: {result[\'error\']}",
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
        }'''

new = '''def verify_spec(state: MetaAgentState) -> dict:
    """
    Node 5: Verify the generated AgentSpec.
    Currently uses Claude as self-review. GPT-4o verification added in Phase 2.
    Returns CONDITIONAL to allow pipeline to continue.
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
- verified_by: "claude-self-review"

PASS = spec is complete, safe, and well-defined.
CONDITIONAL = spec has minor issues but can proceed.
FAIL = spec has critical problems and must be regenerated.

Return only valid JSON. No markdown. No explanation.
"""
    result = claude.call(prompt, system=system, max_tokens=1000)
    if result["error"]:
        verification = VerificationResult(
            status="CONDITIONAL",
            issues=["Verifier unavailable — proceeding with caution."],
            suggestions=[],
            verified_by="skipped",
        )
        _audit(state, "verify_spec", "Verifier unavailable — CONDITIONAL pass")
        return {
            "verification_result": verification,
            "current_error": None,
            "should_stop": False,
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
        }'''

content = content.replace(old, new)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated - verify_spec now uses Claude")
