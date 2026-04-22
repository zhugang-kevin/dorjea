"""
境内大模型 HTTP 客户端封装。
所有生成与校验调用经由此模块；密钥与模型名仅从环境变量读取。
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional
import httpx
from pydantic import BaseModel, Field, field_validator


class AIChatRequest(BaseModel):
    """单次对话补全请求参数。"""

    prompt: str = Field(..., description="用户提示文本")
    system: str = Field(default="", description="系统提示")
    max_tokens: Optional[int] = Field(default=None, description="最大生成 token 数")

    @field_validator("prompt")
    @classmethod
    def _prompt_non_empty(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("提示词不能为空")
        return value


class AIChatResponse(BaseModel):
    """对话补全统一响应结构。"""

    text: str = Field(default="", description="模型输出文本")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    error: Optional[str] = Field(default=None, description="错误信息，成功时为 None")
    provider: str = Field(default="none", description="提供商标识")


def _messages_for_chat(system: str, prompt: str) -> list[dict[str, str]]:
    """构造 chat completions 消息列表。"""
    out: list[dict[str, str]] = []
    if system and system.strip():
        out.append({"role": "system", "content": system})
    out.append({"role": "user", "content": prompt})
    return out


def _parse_chat_completion_payload(data: dict[str, Any]) -> tuple[str, int, int, int]:
    """从标准 chat/completions 形状 JSON 中解析文本与用量。"""
    choices = data.get("choices") or []
    text = ""
    if choices:
        msg = (choices[0] or {}).get("message") or {}
        text = (msg.get("content") or "").strip()
    usage = data.get("usage") or {}
    inp = int(usage.get("prompt_tokens") or 0)
    outp = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or (inp + outp))
    return text, inp, outp, total


def _post_chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    prompt: str,
    max_tokens: int,
    provider_label: str,
) -> AIChatResponse:
    """向兼容 /v1/chat/completions 的端点发起 POST 并解析结果。"""
    try:
        if not api_key:
            return AIChatResponse(
                error="未配置接口密钥，请设置对应环境变量。", provider=provider_label
            )
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": _messages_for_chat(system, prompt),
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text, inp, outp, total = _parse_chat_completion_payload(data)
        return AIChatResponse(
            text=text,
            input_tokens=inp,
            output_tokens=outp,
            total_tokens=total,
            error=None,
            provider=provider_label,
        )
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.text[:500]
        except Exception:
            detail = str(exc)
        return AIChatResponse(
            error=f"接口返回 HTTP 错误：{exc.response.status_code}。详情：{detail}",
            provider=provider_label,
        )
    except httpx.RequestError as exc:
        return AIChatResponse(
            error=f"网络请求失败：{exc!s}", provider=provider_label
        )
    except json.JSONDecodeError as exc:
        return AIChatResponse(
            error=f"响应不是合法 JSON，无法解析：{exc!s}", provider=provider_label
        )
    except Exception as exc:
        return AIChatResponse(
            error=f"调用模型接口时发生异常：{exc!s}", provider=provider_label
        )


class DeepSeekDomesticClient:
    """深度求索（境内）聊天补全客户端。"""

    def __init__(self) -> None:
        """从环境变量初始化默认模型与基础 URL。"""
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.default_max_tokens = 4096

    def call(self, request: AIChatRequest) -> AIChatResponse:
        """执行一次聊天补全请求。"""
        try:
            key = os.getenv("DEEPSEEK_API_KEY", "")
            max_t = request.max_tokens or self.default_max_tokens
            return _post_chat_completions(
                base_url=self._base_url,
                api_key=key,
                model=self.model,
                system=request.system,
                prompt=request.prompt,
                max_tokens=max_t,
                provider_label="deepseek",
            )
        except Exception as exc:
            return AIChatResponse(
                error=f"深度求索客户端异常：{exc!s}", provider="deepseek"
            )


class MoonshotDomesticClient:
    """月之暗面（境内）聊天补全客户端。"""

    def __init__(self) -> None:
        """从环境变量初始化默认模型与基础 URL。"""
        self.model = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
        self._base_url = os.getenv(
            "MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"
        )
        self.default_max_tokens = 4096

    def call(self, request: AIChatRequest) -> AIChatResponse:
        """执行一次聊天补全请求。"""
        try:
            key = os.getenv("MOONSHOT_API_KEY", "")
            max_t = request.max_tokens or self.default_max_tokens
            return _post_chat_completions(
                base_url=self._base_url,
                api_key=key,
                model=self.model,
                system=request.system,
                prompt=request.prompt,
                max_tokens=max_t,
                provider_label="moonshot",
            )
        except Exception as exc:
            return AIChatResponse(
                error=f"月之暗面客户端异常：{exc!s}", provider="moonshot"
            )


class DashScopeDomesticClient:
    """阿里云通义千问兼容模式（境内）客户端。"""

    def __init__(self) -> None:
        """从环境变量初始化默认模型与基础 URL。"""
        self.model = os.getenv("DASHSCOPE_MODEL", "qwen-turbo")
        self._base_url = os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.default_max_tokens = 4096

    def call(self, request: AIChatRequest) -> AIChatResponse:
        """执行一次聊天补全请求。"""
        try:
            key = os.getenv("DASHSCOPE_API_KEY", "")
            max_t = request.max_tokens or self.default_max_tokens
            return _post_chat_completions(
                base_url=self._base_url,
                api_key=key,
                model=self.model,
                system=request.system,
                prompt=request.prompt,
                max_tokens=max_t,
                provider_label="dashscope",
            )
        except Exception as exc:
            return AIChatResponse(
                error=f"通义千问兼容接口异常：{exc!s}", provider="dashscope"
            )


class ZhipuDomesticClient:
    """智谱清言（境内）聊天补全客户端。"""

    def __init__(self) -> None:
        """从环境变量初始化默认模型与基础 URL。"""
        self.model = os.getenv("ZHIPU_MODEL", "glm-4-flash")
        self._base_url = os.getenv(
            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
        )
        self.default_max_tokens = 4096

    def call(self, request: AIChatRequest) -> AIChatResponse:
        """执行一次聊天补全请求。"""
        try:
            key = os.getenv("ZHIPU_API_KEY", "")
            max_t = request.max_tokens or self.default_max_tokens
            return _post_chat_completions(
                base_url=self._base_url,
                api_key=key,
                model=self.model,
                system=request.system,
                prompt=request.prompt,
                max_tokens=max_t,
                provider_label="zhipu",
            )
        except Exception as exc:
            return AIChatResponse(
                error=f"智谱客户端异常：{exc!s}", provider="zhipu"
            )


def _make_named_client(name: str):
    """按名称构造境内客户端实例。"""
    key = name.strip().lower()
    if key == "deepseek":
        return DeepSeekDomesticClient()
    if key == "moonshot":
        return MoonshotDomesticClient()
    if key == "dashscope":
        return DashScopeDomesticClient()
    if key == "zhipu":
        return ZhipuDomesticClient()
    return DeepSeekDomesticClient()


class PrimaryChatClient:
    """主生成模型客户端（默认深度求索，可通过 PRIMARY_CHAT_BACKEND 切换）。"""

    def __init__(self) -> None:
        """根据环境变量选择后端并同步默认模型名。"""
        backend = os.getenv("PRIMARY_CHAT_BACKEND", "deepseek").strip().lower()
        self._impl = _make_named_client(backend)

    @property
    def model(self) -> str:
        """当前主模型名称（与各后端实现上的 model 字段一致）。"""
        return self._impl.model

    @model.setter
    def model(self, value: str) -> None:
        """允许运行时覆盖模型名（例如按智能体配置）。"""
        self._impl.model = value

    def call(self, request: AIChatRequest) -> AIChatResponse:
        """转发到当前后端执行请求。"""
        try:
            return self._impl.call(request)
        except Exception as exc:
            return AIChatResponse(
                error=f"主模型调用失败：{exc!s}",
                provider="primary",
            )


class VerifierChatClient:
    """独立校验用模型客户端（默认月之暗面，可通过 VERIFIER_CHAT_BACKEND 切换）。"""

    def __init__(self) -> None:
        """根据环境变量选择后端并同步默认模型名。"""
        backend = os.getenv("VERIFIER_CHAT_BACKEND", "moonshot").strip().lower()
        self._impl = _make_named_client(backend)

    @property
    def model(self) -> str:
        """当前校验模型名称。"""
        return self._impl.model

    @model.setter
    def model(self, value: str) -> None:
        """允许运行时覆盖校验模型名。"""
        self._impl.model = value

    def call(self, request: AIChatRequest) -> AIChatResponse:
        """转发到校验后端执行请求。"""
        try:
            return self._impl.call(request)
        except Exception as exc:
            return AIChatResponse(
                error=f"校验模型调用失败：{exc!s}",
                provider="verifier",
            )
