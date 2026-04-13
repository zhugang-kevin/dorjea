with open("agents/meta_agent/nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add prompts import after existing imports
old_import = "from self_token.budget_manager import track_tokens, is_within_budget"
new_import = """from self_token.budget_manager import track_tokens, is_within_budget
from agents.meta_agent.prompts import (
    GENERATE_SPEC_SYSTEM,
    PARSE_REQUEST_SYSTEM,
    APPROVED_TOOLS,
    build_generate_spec_user_message,
    build_parse_request_user_message,
)"""
content = content.replace(old_import, new_import)

# Fix parse_request node - replace inline system and prompt with role-neutral versions
old_parse_system = '''    system = (
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
    result = claude.call(prompt, system=system)'''

new_parse_system = '''    result = claude.call(
        build_parse_request_user_message(founder_request),
        system=PARSE_REQUEST_SYSTEM,
    )'''

content = content.replace(old_parse_system, new_parse_system)

# Fix generate_spec node - replace inline system and prompt with role-neutral versions
old_gen_system = '''    system = (
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
    result = claude.call(prompt, system=system, max_tokens=2000)'''

new_gen_system = '''    result = claude.call(
        build_generate_spec_user_message(task_spec, []),
        system=GENERATE_SPEC_SYSTEM,
        max_tokens=2000,
    )'''

content = content.replace(old_gen_system, new_gen_system)

with open("agents/meta_agent/nodes.py", "w", encoding="utf-8") as f:
    f.write(content)
print("nodes.py updated with role-neutral prompts")
