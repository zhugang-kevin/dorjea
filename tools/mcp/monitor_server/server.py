from fastmcp import FastMCP
from self_monitoring.health_monitor import get_factory_dashboard
from self_monitoring.drift_detector import get_drift_status
from self_monitoring.agent_performance import get_performance_summary
from self_token.budget_manager import get_daily_usage, is_within_daily_budget

mcp = FastMCP("monitor-server")

@mcp.tool()
def get_system_health() -> dict:
    return get_factory_dashboard()

@mcp.tool()
def get_drift_report() -> dict:
    return get_drift_status()

@mcp.tool()
def get_agent_performance_report() -> dict:
    return get_performance_summary()

@mcp.tool()
def get_token_usage() -> dict:
    return {"daily_tokens_used": get_daily_usage(), "within_budget": is_within_daily_budget()}

if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8004)
