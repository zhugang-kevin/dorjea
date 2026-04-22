"""Shared reliability layer for model calls and workflow execution."""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Callable, Optional

from pydantic import BaseModel, Field

from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry
from agents.runtime.ai_clients import AIChatRequest, AIChatResponse
from agents.runtime.model_router import model_router


class ReliabilityPolicy(BaseModel):
    max_attempts: int = 3
    retry_backoff_seconds: float = 1.0
    min_output_chars: int = 24
    require_json: bool = False
    fallback_to_router: bool = True
    use_cache: bool = True
    cache_ttl_seconds: int = 300
    min_confidence: float = 0.55


class ReliabilityResult(BaseModel):
    response: AIChatResponse
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attempts: int = 1
    from_cache: bool = False
    used_fallback: bool = False
    validation_errors: list[str] = Field(default_factory=list)


_CACHE: dict[str, tuple[float, ReliabilityResult]] = {}


def _audit(task_id: str, agent_id: str, action: str, details: dict, success: bool) -> None:
    write_audit_entry(
        AuditEntry(
            agent_id=agent_id,
            task_id=task_id,
            action=action,
            details=details,
            success=success,
        )
    )


def _cache_key(request: AIChatRequest) -> str:
    raw = json.dumps(request.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_response(
    response: AIChatResponse,
    policy: ReliabilityPolicy,
    validator: Optional[Callable[[str], Optional[list[str]]]],
) -> list[str]:
    errors: list[str] = []
    text = (response.text or "").strip()
    if response.error:
        errors.append(response.error)
        return errors
    if len(text) < policy.min_output_chars:
        errors.append("输出过短，缺少稳定可用内容。")
    if policy.require_json:
        try:
            json.loads(text)
        except Exception as exc:
            errors.append(f"输出不是合法 JSON：{exc!s}")
    if validator is not None:
        custom = validator(text)
        if custom:
            errors.extend(custom)
    return errors


def _confidence_for(response: AIChatResponse, validation_errors: list[str], attempts: int) -> float:
    if response.error:
        return 0.0
    text = (response.text or "").strip()
    score = 0.92
    if len(text) < 80:
        score -= 0.18
    if validation_errors:
        score -= min(0.45, 0.15 * len(validation_errors))
    score -= max(0, attempts - 1) * 0.08
    return max(0.0, min(1.0, round(score, 3)))


def call_with_reliability(
    *,
    request: AIChatRequest,
    task_id: str,
    agent_id: str,
    client,
    policy: ReliabilityPolicy | None = None,
    validator: Optional[Callable[[str], Optional[list[str]]]] = None,
) -> ReliabilityResult:
    policy = policy or ReliabilityPolicy()
    key = _cache_key(request)

    if policy.use_cache and key in _CACHE:
        ts, cached = _CACHE[key]
        if time.time() - ts <= policy.cache_ttl_seconds:
            _audit(
                task_id,
                agent_id,
                "RELIABILITY_CACHE_HIT",
                {"confidence": cached.confidence, "provider": cached.response.provider},
                True,
            )
            return cached.model_copy(update={"from_cache": True})
        _CACHE.pop(key, None)

    last_response = AIChatResponse(error="尚未执行", provider="none")
    last_errors: list[str] = ["尚未执行"]
    used_fallback = False

    for attempt in range(1, max(1, policy.max_attempts) + 1):
        response = client.call(request)
        fallback_this_round = False
        errors = _validate_response(response, policy, validator)

        if errors and policy.fallback_to_router and attempt == policy.max_attempts:
            response = model_router.call(
                prompt=request.prompt,
                system=request.system,
                max_tokens=request.max_tokens or 2000,
                task_id=task_id,
            )
            fallback_this_round = True
            used_fallback = True
            errors = _validate_response(response, policy, validator)

        confidence = _confidence_for(response, errors, attempt)
        details = {
            "attempt": attempt,
            "provider": response.provider,
            "confidence": confidence,
            "validation_errors": errors[:3],
            "used_fallback": fallback_this_round,
        }
        _audit(
            task_id,
            agent_id,
            "RELIABILITY_ATTEMPT",
            details,
            success=not errors,
        )

        result = ReliabilityResult(
            response=response,
            confidence=confidence,
            attempts=attempt,
            from_cache=False,
            used_fallback=used_fallback,
            validation_errors=errors,
        )
        if not errors and confidence >= policy.min_confidence:
            if policy.use_cache:
                _CACHE[key] = (time.time(), result)
            return result

        last_response = response
        last_errors = errors or ["未知错误"]
        if attempt < policy.max_attempts:
            time.sleep(policy.retry_backoff_seconds * attempt)

    return ReliabilityResult(
        response=last_response,
        confidence=_confidence_for(last_response, last_errors, policy.max_attempts),
        attempts=policy.max_attempts,
        from_cache=False,
        used_fallback=used_fallback,
        validation_errors=last_errors,
    )
