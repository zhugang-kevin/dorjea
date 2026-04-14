APPROVED_TOOLS = [
    'filesystem_server',
    'registry_server',
    'github_server',
    'web_search',
    'email',
    'calendar',
]

GENERATE_SPEC_SYSTEM = (
    'You are the AI Factory Meta-Agent specification engine. '
    'Generate a complete 16-component Agent DNA Schema from a TaskSpec. '
    'You have no role. You produce agents for any domain. '
    'Return ONLY valid JSON. No markdown. No backticks. No explanation. '
    'Every field is mandatory. Shallow definitions are rejected. '
    'SCHEMA: agent_name, version, department, mission, '
    'domain_knowledge (list of 8+ knowledge domains), '
    'competencies (list of 6+ professional capabilities), '
    'technical_skills (list of 5+ technical abilities), '
    'experience_patterns (list of 4+ simulated experience patterns), '
    'reasoning_framework (list of reasoning approaches), '
    'decision_rules (list of IF/THEN decision rules min 4), '
    'execution_workflow (ordered list of steps min 5), '
    'allowed_tools (from approved list only), '
    'memory_interface (read and write definitions), '
    'communication_protocol (message schema), '
    'quality_standards (list of measurable benchmarks min 4), '
    'responsibilities (list of 6+ specific responsibilities), '
    'non_responsibilities (list of 4+ hard boundaries), '
    'verification_logic (list of self-check questions min 4), '
    'observability (log fields and metrics to track), '
    'escalation_triggers (list of 4+ escalation conditions), '
    'token_budget (integer 5000-20000), '
    'default_model (claude-sonnet-4-6), '
    'fallback_model (gpt-5), '
    'memory_policy (session_only|persistent|none), '
    'retry_policy ({max_attempts:3, backoff_seconds:2})'
)

PARSE_REQUEST_SYSTEM = (
    'You are the AI Factory request parser. '
    'Convert founder plain-language into a structured TaskSpec JSON. '
    'Return ONLY valid JSON. No markdown. No explanation. '
    'Schema: agent_name, agent_role, agent_mission, department, '
    'allowed_tools, token_budget, founder_request'
)

def build_generate_spec_user_message(task_spec, existing_agent_names):
    return (
        '## TaskSpec' + chr(10) + task_spec.model_dump_json(indent=2) +
        chr(10) + chr(10) + '## Approved tools (use only these): ' + str(APPROVED_TOOLS) +
        chr(10) + '## Existing agents (do not duplicate): ' + str(existing_agent_names) +
        chr(10) + chr(10) + 'Generate the complete 16-component Agent DNA JSON now. Every field mandatory. Be specific and professional.'
    )

def build_parse_request_user_message(raw_instruction):
    return 'Founder instruction: ' + raw_instruction + chr(10) + chr(10) + 'Parse into TaskSpec JSON now.'
