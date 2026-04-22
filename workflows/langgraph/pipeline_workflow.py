"""多阶段流水线工作流：依次调用境内主模型完成各阶段任务。"""
import asyncio
from datetime import datetime

from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from agents.runtime.ai_clients import AIChatRequest, PrimaryChatClient
from agents.runtime.reliability import ReliabilityPolicy, call_with_reliability

primary_llm = PrimaryChatClient()


def log(task_id, action, details):
    """写入流水线操作日志。"""
    write_audit_entry(
        AuditEntry(
            agent_id="pipeline",
            task_id=task_id,
            action=action,
            details=details,
        )
    )


def run_stage(task_id, stage_name, instruction, context=""):
    """
    执行单个流水线阶段。

    返回 (output_text, tokens_used)；失败时 output_text 为 None。
    """
    full_prompt = instruction
    if context:
        full_prompt = (
            "Previous stage output:"
            + chr(10)
            + context
            + chr(10)
            + chr(10)
            + instruction
        )
    try:
        reliable = call_with_reliability(
            request=AIChatRequest(prompt=full_prompt, system="", max_tokens=2000),
            task_id=task_id,
            agent_id="pipeline",
            client=primary_llm,
            policy=ReliabilityPolicy(min_output_chars=32, min_confidence=0.55),
        )
        result = reliable.response
    except Exception as exc:
        log(task_id, stage_name + "_FAILED", {"error": str(exc)})
        return None, 0
    if result.error:
        log(task_id, stage_name + "_FAILED", {"error": result.error})
        return None, 0
    log(task_id, stage_name + "_COMPLETE", {"tokens": result.total_tokens})
    return result.text, result.total_tokens


def run_build_feature_pipeline(feature_description, task_id=None):
    """从功能描述运行内置的多阶段构建流水线。"""
    if not task_id:
        task_id = "pipeline_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print("Pipeline starting: " + feature_description)
    total_tokens = 0
    results = {}

    print("Stage 1: Planning...")
    plan, tokens = run_stage(
        task_id,
        "PLAN",
        "Break this feature into 3-5 specific development tasks. Be concise and clear. Feature: "
        + feature_description,
    )
    if not plan:
        return {"status": "FAILED", "stage": "planning", "task_id": task_id}
    results["planning"] = plan
    total_tokens += tokens

    print("Stage 2: Implementation...")
    impl, tokens = run_stage(
        task_id,
        "IMPLEMENT",
        "Write a Python implementation plan for these tasks. Include key functions needed.",
        context=plan,
    )
    if not impl:
        return {"status": "FAILED", "stage": "implementation", "task_id": task_id}
    results["implementation"] = impl
    total_tokens += tokens

    print("Stage 3: Review...")
    review, tokens = run_stage(
        task_id,
        "REVIEW",
        "Review this implementation plan. Identify any risks, missing pieces, or improvements needed.",
        context=impl,
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


async def run_build_feature_pipeline_async(feature_description, task_id=None):
    """异步包装：在线程池中运行同步流水线。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_build_feature_pipeline(feature_description, task_id),
    )


if __name__ == "__main__":
    demo = run_build_feature_pipeline(
        "为智能体操作系统 API 增加 CSV 导出端点"
    )
    print("Status: " + demo["status"])
    print("Tokens used: " + str(demo.get("total_tokens", 0)))
