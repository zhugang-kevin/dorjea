# Token Budget — Dorjea AI Factory

## Per-Task Budget
Maximum tokens per agent creation: 20,000
Daily total budget: 100,000

## Cost Estimates (Claude Sonnet 4.6)
| Node | Estimated Tokens |
|---|---|
| parse_request | 500-1,000 |
| validate_spec | 100-200 |
| check_registry | 50-100 |
| generate_spec | 2,000-4,000 |
| verify_spec | 1,500-3,000 |
| generate_code | 3,000-6,000 |
| run_tests | 200-500 |
| register_agent | 50-100 |
| return_report | 100-200 |
| TOTAL | 7,500-15,100 |

## Cost Per Agent Creation
Estimated: USD 0.15 - 0.35 per agent

## Monitoring
- Metrics log: logs/metrics.jsonl
- Health endpoint: GET /health
- Metrics endpoint: GET /metrics

## Rules
- Hard ceiling: 20,000 tokens per task
- If exceeded: halt, save checkpoint, request approval
- Daily budget: 100,000 tokens
- If exceeded: API returns 429 until next day