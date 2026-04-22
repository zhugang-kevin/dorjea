import os
import json
from datetime import datetime
from pathlib import Path

METRICS_PATH = Path(os.getenv("METRICS_LOG_PATH", "logs/metrics.jsonl"))
MAX_TOKENS_PER_TASK = int(os.getenv("MAX_TOKENS_PER_TASK", "10000"))
DAILY_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", "50000"))


def track_tokens(agent_id, task_id, model, prompt_tokens, completion_tokens):
    total = prompt_tokens + completion_tokens
    budget_pct = round(total / MAX_TOKENS_PER_TASK * 100, 1)
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent_id": agent_id,
        "task_id": task_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "budget": MAX_TOKENS_PER_TASK,
        "budget_used_pct": budget_pct,
    }
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + chr(10))
    return entry


def is_within_budget(tokens_used, budget=None):
    limit = budget or MAX_TOKENS_PER_TASK
    return tokens_used < limit


def compress_prompt(prompt, max_chars=12000):
    if len(prompt) <= max_chars:
        return prompt
    half = max_chars // 2
    return prompt[:half] + chr(10) + "[...content compressed...]" + chr(10) + prompt[-half:]


def get_daily_usage(hours=48):
    if not METRICS_PATH.exists():
        return 0
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    total = 0
    try:
        with open(METRICS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("timestamp", "") >= cutoff:
                    total += entry.get("total_tokens", 0)
    except Exception:
        pass
    return total


def is_within_daily_budget():
    return get_daily_usage() < DAILY_BUDGET