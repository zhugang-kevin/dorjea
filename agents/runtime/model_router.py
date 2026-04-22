"""
多境内模型按顺序降级调用；失败时写入操作日志。
"""
from __future__ import annotations

import os
from typing import List

from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from agents.runtime.ai_clients import (
    AIChatRequest,
    AIChatResponse,
    DashScopeDomesticClient,
    DeepSeekDomesticClient,
    MoonshotDomesticClient,
    ZhipuDomesticClient,
)


def _default_provider_order(prompt: str = "") -> List[str]:
    """Use a cheap-first order for short prompts and a stronger order for long prompts."""
    prompt_len = len((prompt or "").strip())
    if prompt_len > int(os.getenv("MODEL_ROUTER_LONG_PROMPT_THRESHOLD", "1800")):
        raw = os.getenv("MODEL_ROUTER_LONG_ORDER", "moonshot,zhipu,dashscope,deepseek")
    else:
        raw = os.getenv("MODEL_ROUTER_ORDER", "dashscope,deepseek,moonshot,zhipu")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _client_for_provider(name: str):
    """按提供方标识构造对应客户端实例。"""
    key = name.strip().lower()
    if key == "dashscope":
        return DashScopeDomesticClient()
    if key == "moonshot":
        return MoonshotDomesticClient()
    if key == "deepseek":
        return DeepSeekDomesticClient()
    if key == "zhipu":
        return ZhipuDomesticClient()
    return DeepSeekDomesticClient()


def call_with_fallback(
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
    task_id: str = "routing",
) -> AIChatResponse:
    """
    按配置顺序尝试多个境内模型，返回首次成功结果；
    全部失败时返回带中文错误说明的响应。
    """
    last_error: str | None = None
    request = AIChatRequest(prompt=prompt, system=system, max_tokens=max_tokens)
    for provider in _default_provider_order(prompt):
        client = _client_for_provider(provider)
        try:
            result = client.call(request)
            if result.error:
                last_error = result.error
                write_audit_entry(
                    AuditEntry(
                        agent_id="model_router",
                        task_id=task_id,
                        action="PROVIDER_FAILED",
                        details={
                            "provider": provider,
                            "error": str(last_error)[:200],
                        },
                        success=False,
                    )
                )
                continue
            write_audit_entry(
                AuditEntry(
                    agent_id="model_router",
                    task_id=task_id,
                    action="PROVIDER_SUCCESS",
                    details={"provider": provider, "tokens": result.total_tokens},
                    success=True,
                )
            )
            return result.model_copy(update={"provider": provider})
        except Exception as exc:
            last_error = str(exc)
            write_audit_entry(
                AuditEntry(
                    agent_id="model_router",
                    task_id=task_id,
                    action="PROVIDER_EXCEPTION",
                    details={"provider": provider, "error": str(exc)[:200]},
                    success=False,
                )
            )
            continue
    msg = last_error or "未知错误"
    return AIChatResponse(
        text="",
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        error=f"所有境内模型均不可用，最后一次错误：{msg}",
        provider="none",
    )


model_router = type(
    "ModelRouter",
    (),
    {"call": staticmethod(call_with_fallback)},
)()
