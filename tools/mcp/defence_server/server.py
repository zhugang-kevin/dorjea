from fastmcp import FastMCP
from self_defence.injection_detector import is_safe, sanitize
from self_defence.rate_limiter import rate_limiter
from self_governance.governance_compliance import check_governance_compliance, run_governance_audit

mcp = FastMCP("defence-server")

@mcp.tool()
def check_input_safety(text: str, agent_id: str = "system") -> dict:
    safe, reason = is_safe(text, agent_id=agent_id)
    return {"safe": safe, "reason": reason}

@mcp.tool()
def check_rate_limit(agent_id: str = "global") -> dict:
    allowed = rate_limiter.is_allowed(agent_id)
    remaining = rate_limiter.get_remaining(agent_id)
    return {"allowed": allowed, "remaining_tokens": remaining}

@mcp.tool()
def check_action_compliance(agent_name: str, action: str) -> dict:
    ok, violations = check_governance_compliance(agent_name, action)
    return {"compliant": ok, "violations": violations}

@mcp.tool()
def run_full_governance_audit() -> dict:
    return run_governance_audit()

if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8005)
