content = """
import os
import json
from datetime import datetime
from pathlib import Path

REPRODUCTIONS_DIR = Path("logs/reproductions")


def save_execution_record(task_id, agent_id, node_name, model,
                          system_prompt, user_prompt, output, tokens_used):
    record = {
        "task_id": task_id,
        "agent_id": agent_id,
        "node_name": node_name,
        "timestamp": datetime.utcnow().isoformat(),
        "model": model,
        "temperature": 0.0,
        "system_prompt_hash": str(hash(system_prompt)),
        "system_prompt_preview": system_prompt[:200],
        "user_prompt_preview": user_prompt[:200],
        "output_preview": str(output)[:200],
        "tokens_used": tokens_used,
    }
    REPRODUCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    record_path = REPRODUCTIONS_DIR / (task_id + "_" + node_name + ".json")
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return str(record_path)


def load_execution_record(task_id, node_name):
    record_path = REPRODUCTIONS_DIR / (task_id + "_" + node_name + ".json")
    if not record_path.exists():
        return None
    with open(record_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_execution_records(task_id):
    if not REPRODUCTIONS_DIR.exists():
        return []
    records = []
    for f in REPRODUCTIONS_DIR.glob(task_id + "_*.json"):
        records.append(f.stem)
    return sorted(records)
"""

with open("agents/meta_agent/reproducibility.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("reproducibility.py created")
