import json
import time
import httpx
from pathlib import Path
from datetime import datetime

TASKS_FILE = Path("evals/datasets/meta_agent_tasks.jsonl")
REPORTS_DIR = Path("evals/reports")
API_URL = "http://127.0.0.1:8000/agents/create"


def load_tasks():
    tasks = []
    with open(TASKS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line.strip()))
    return tasks


def run_single_eval(task):
    start = time.time()
    try:
        response = httpx.post(
            API_URL,
            json={"request": task["request"]},
            timeout=120,
        )
        elapsed = round(time.time() - start, 2)
        if response.status_code == 200:
            result = response.json()
            passed = result.get("status") == "SUCCESS"
            return {
                "task_id": task["task_id"],
                "status": result.get("status"),
                "agent_name": result.get("agent_name"),
                "tokens_used": result.get("total_tokens_used", 0),
                "elapsed_seconds": elapsed,
                "passed": passed,
                "errors": result.get("errors", []),
            }
        else:
            return {
                "task_id": task["task_id"],
                "status": "HTTP_ERROR",
                "agent_name": "unknown",
                "tokens_used": 0,
                "elapsed_seconds": elapsed,
                "passed": False,
                "errors": [str(response.status_code)],
            }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "task_id": task["task_id"],
            "status": "EXCEPTION",
            "agent_name": "unknown",
            "tokens_used": 0,
            "elapsed_seconds": elapsed,
            "passed": False,
            "errors": [str(e)],
        }


def run_all_evals(max_tasks=None):
    tasks = load_tasks()
    if max_tasks:
        tasks = tasks[:max_tasks]

    print("Running " + str(len(tasks)) + " eval tasks...")
    results = []

    for i, task in enumerate(tasks):
        print("Task " + str(i+1) + "/" + str(len(tasks)) + ": " + task["task_id"])
        result = run_single_eval(task)
        results.append(result)
        status = "PASSED" if result["passed"] else "FAILED"
        print("  " + status + " | " + str(result["tokens_used"]) + " tokens | " + str(result["elapsed_seconds"]) + "s")
        time.sleep(2)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    total_tokens = sum(r["tokens_used"] for r in results)

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_tasks": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1),
        "total_tokens": total_tokens,
        "results": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / ("eval_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("")
    print("========================================")
    print("EVAL COMPLETE: " + str(passed) + "/" + str(total) + " passed (" + str(report["pass_rate"]) + "%)")
    print("Total tokens: " + str(total_tokens))
    print("Report saved: " + str(report_path))
    print("========================================")
    return report


if __name__ == "__main__":
    run_all_evals()