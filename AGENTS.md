# AGENTS.md — Dorjea AI Factory Company Constitution

## MISSION
Build a Meta-Agent platform that creates, manages, and orchestrates AI agents
for a solo AI company. The founder describes what they want in plain English.
The Meta-Agent handles everything else.

## 20 NON-NEGOTIABLE RULES
1.  Never create a new agent if an existing one can be extended.
2.  Never allow the same agent to author and approve the same change.
3.  Never merge code without passing tests + second-model review + FounderReport.
4.  Never grant more tool access than the minimum required.
5.  Never allow an agent to use production credentials by default.
6.  Never allow silent scope expansion.
7.  Never allow silent retries beyond the retry policy.
8.  Never allow free-form outputs when a schema exists.
9.  Never let docs drift — behaviour change = doc change in the same task.
10. Never accept looks good as validation — require evidence.
11. Never replace a stable workflow with a clever one without benchmarks.
12. Never create long-lived memory unless explicitly categorized and versioned.
13. Never store secrets in prompts, specs, logs, or eval data.
14. Never create a specialist agent without: mission, boundaries, allowed tools, input schema, output schema, success metrics, escalation path.
15. Never let an agent call another agent without a typed TaskEnvelope.
16. Never let an agent change its own policy file.
17. Never treat benchmark wins as production approval without real-task evals.
18. Never bypass the founder on security, billing, deletion, or release policy.
19. Never create agent chains longer than necessary — prefer fewer steps.
20. Never optimize for elegance over recoverability.

## AGENT LIFECYCLE
Create -> Register -> Validate -> Activate -> Monitor -> Update -> Archive

## FORBIDDEN ACTIONS
- Modify folder structure
- Install new packages
- Change port assignments
- Delete registry entries
- Access production credentials
- Call another agent directly
- Create new environment variables
- Push code to main branch directly

## REQUIRED FOR EVERY AGENT DEFINITION
- agent_name, version, mission, allowed_tools, token_budget
- input_schema (Pydantic model), output_schema (Pydantic model)
- retry_policy, escalation_triggers, status

## TOKEN BUDGETS
- Meta-Agent: 20,000 tokens per task
- Research Agent: 15,000 tokens per task
- Coding Agent: 20,000 tokens per task
- Marketing Agent: 10,000 tokens per task
- Support Agent: 5,000 tokens per task
- Daily total: 100,000 tokens

## TOOL PERMISSIONS
- filesystem_server: read_file, write_file, create_directory, list_directory, file_exists
- registry_server: register_agent, get_agent, list_agents, update_status, check_duplicate
- github_server: create_branch, commit_files

## ERROR HANDLING POLICY
- Agent fails 3 times: stop workflow, return FounderReport
- Tool server down: save checkpoint, report to founder, wait
- Token limit exceeded: halt, save state, request approval
- Forbidden action: halt immediately, log, flag agent as requires_review
- Schema validation fails: reject output, report error

## DEFINITION OF DONE
1. All pytest tests pass
2. verify.ps1 runs with 0 errors
3. Audit log has entry for session
4. Agent in registry with status ACTIVE
5. FounderReport returned with rollback command
6. No TODO or placeholder in any .py file
7. No hardcoded secrets in any file
8. VERIFY command returned True

## COMMUNICATION PROTOCOL
- All agent communication goes through LangGraph state
- All messages are typed Pydantic models
- All actions logged to logs/audit.jsonl
- Founder receives FounderReport at end of every task
