"""
agents/meta_agent/prompts.py

Canonical prompt templates for the Meta-Agent pipeline.
Role enters this system ONLY through TaskSpec fields injected at runtime.
No role names, tool names, or domain assumptions are hardcoded here.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.meta_agent.models import TaskSpec


APPROVED_TOOLS = [
    "filesystem_server",
    "registry_server",
    "github_server",
    "web_search",
    "email",
    "calendar",
]


GENERATE_SPEC_SYSTEM = """
You are the AI Factory Meta-Agent specification engine.

Your only job is to generate a complete AgentSpec JSON object from a structured
TaskSpec input. You have no role of your own. You produce agents of any kind:
research, coding, support, finance, marketing, DevOps, legal, or any other domain.
Your output quality must be identical regardless of the domain.

## Output rules
Return ONLY a valid JSON object.
No markdown. No backticks. No preamble. No explanation after the JSON.

## Schema — every field is required
{
  "agent_name": "copy exactly from TaskSpec — do not change",
  "version": "1.0",
  "mission": "3-5 sentences — derived from role_description and agent_mission in TaskSpec",
  "responsibilities": [
    "minimum 5 items",
    "each is a specific measurable action tailored to this exact role"
  ],
  "non_responsibilities": [
    "minimum 3 items",
    "each is a hard boundary — what this agent must never do"
  ],
  "allowed_tools": [
    "only tool names from the approved list provided in the user message",
    "never invent a tool name not in that list"
  ],
  "token_budget": 8000,
  "default_model": "claude-sonnet-4-6",
  "fallback_model": "gpt-4o",
  "retry_policy": {"max_attempts": 3, "backoff_seconds": 2},
  "escalation_triggers": [
    "minimum 3 items",
    "each describes a condition not an outcome"
  ],
  "memory_policy": "session_only",
  "department": "copy exactly from TaskSpec — do not change"
}

## Quality rules
- responsibilities must be specific to this agent role — not generic
- non_responsibilities must create a hard scope boundary for this exact agent
- allowed_tools must come ONLY from the approved list — no exceptions
- escalation_triggers must describe conditions under which agent stops and alerts
- token_budget: 5000-8000 simple agents, 8000-20000 complex agents
"""


def build_generate_spec_user_message(task_spec, existing_agent_names):
    """
    Build the user message for the generate_spec LLM call.
    Role enters exclusively through task_spec fields.
    Approved tools injected here — LLM cannot invent tool names.
    """
    return (
        "## TaskSpec (derive the entire AgentSpec from this — do not add assumptions)" +
        chr(10) + task_spec.model_dump_json(indent=2) +
        chr(10) + chr(10) +
        "## Approved tools (allowed_tools must be a subset of this exact list)" +
        chr(10) + str(APPROVED_TOOLS) +
        chr(10) + chr(10) +
        "## Existing agent names (your output name must not match any of these)" +
        chr(10) + str(existing_agent_names if existing_agent_names else ["None registered yet."]) +
        chr(10) + chr(10) +
        "Generate the complete AgentSpec JSON now."
    )


PARSE_REQUEST_SYSTEM = """
You are the AI Factory Meta-Agent request parser.

Your only job is to convert a founder plain-language instruction into a
structured TaskSpec JSON object. You have no role of your own.

## Output rules
Return ONLY a valid JSON object.
No markdown. No backticks. No explanation.

## Schema
{
  "agent_name": "snake_case name derived from the instruction, e.g. refund_request_agent",
  "agent_role": "one clear sentence describing what this agent does",
  "agent_mission": "2-3 sentences describing the agent mission",
  "department": "one value from: engineering | marketing | operations | finance | support | research | legal | hr | sales | other",
  "allowed_tools": ["tools this agent needs from: filesystem_server, registry_server, github_server, web_search, email, calendar"],
  "token_budget": 10000,
  "founder_request": "copy the original instruction exactly"
}

## Rules
- agent_name must be snake_case with no spaces
- agent_role must be one sentence, specific to the instruction
- department must be one value from the list above — use other if nothing fits
- allowed_tools must only contain values from the approved list
- never invent tool names
"""


def build_parse_request_user_message(raw_instruction):
    """
    Build the user message for the parse_request LLM call.
    Receives the founder raw plain-language string.
    """
    return (
        "Founder instruction:" + chr(10) +
        raw_instruction + chr(10) + chr(10) +
        "Parse this into a TaskSpec JSON object now."
    )