content = """
import asyncio
import os
from datetime import datetime
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from agents.runtime.ai_clients import ClaudeClient

claude = ClaudeClient()


def log(task_id, action, details):
    write_audit_entry(AuditEntry(
        agent_id="pipeline",
        task_id=task_id,
        action=action,
        details=details,
    ))


def run_stage(task_id, stage_name, instruction, context=""):
    full_prompt = instruction
    if context:
        full_prompt = "Previous stage output:" + chr(10) + context + chr(10) + chr(10) + instruction
    result = claude.call(full_prompt, max_tokens=2000)
    if result["error"]:
        log(task_id, stage_name + "_FAILED", {"error": result["error"]})
        return None, 0
    log(task_id, stage_name + "_COMPLETE", {"tokens": result["total_tokens"]})
    return result["text"], result["total_tokens"]


def run_build_feature_pipeline(feature_description, task_id=None):
    if not task_id:
        task_id = "pipeline_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print("Pipeline starting: " + feature_description)
    total_tokens = 0
    results = {}

    print("Stage 1: Planning...")
    plan, tokens = run_stage(
        task_id, "PLAN",
        "Break this feature into 3-5 specific development tasks. Be concise and clear. Feature: " + feature_description
    )
    if not plan:
        return {"status": "FAILED", "stage": "planning", "task_id": task_id}
    results["planning"] = plan
    total_tokens += tokens

    print("Stage 2: Implementation...")
    impl, tokens = run_stage(
        task_id, "IMPLEMENT",
        "Write a Python implementation plan for these tasks. Include key functions needed.",
        context=plan
    )
    if not impl:
        return {"status": "FAILED", "stage": "implementation", "task_id": task_id}
    results["implementation"] = impl
    total_tokens += tokens

    print("Stage 3: Review...")
    review, tokens = run_stage(
        task_id, "REVIEW",
        "Review this implementation plan. Identify any risks, missing pieces, or improvements needed.",
        context=impl
    )
    if not review:
        return {"status": "FAILED", "stage": "review", "task_id": task_id}
    results["review"] = review
    total_tokens += tokens

    print("Pipeline complete. Total tokens: " + str(total_tokens))
    return {
        "status": "SUCCESS",
        "task_id": task_id,
        "feature": feature_description,
        "stages_completed": 3,
        "total_tokens": total_tokens,
        "results": {k: v[:200] for k, v in results.items()},
    }


if __name__ == "__main__":
    result = run_build_feature_pipeline(
        "Add a CSV export endpoint to the AI Factory API"
    )
    print("Status: " + result["status"])
    print("Tokens used: " + str(result.get("total_tokens", 0)))
"""

with open("workflows/langgraph/pipeline_workflow.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("pipeline_workflow.py created")
