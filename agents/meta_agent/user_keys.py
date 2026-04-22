"""User-managed AI provider keys with scoped access and strong at-rest encryption."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from agents.meta_agent.plan_enforcement import require_feature, resolve_scoped_user_email

router = APIRouter(
    prefix="/user-keys",
    tags=["User API Keys"],
    dependencies=[Depends(require_feature("user_keys"))],
)

USER_KEYS_FILE = Path("memory") / "user_api_keys.jsonl"

SUPPORTED_PROVIDERS = {
    "deepseek": {
        "name": "深度求索",
        "prefix": "sk-",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "icon": "DS",
    },
    "moonshot": {
        "name": "月之暗面",
        "prefix": "sk-",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "base_url": os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"),
        "icon": "MS",
    },
    "dashscope": {
        "name": "通义千问",
        "prefix": "sk-",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "base_url": os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        "icon": "QW",
    },
    "zhipu": {
        "name": "智谱清言",
        "prefix": "",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4-air"],
        "base_url": os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        "icon": "GLM",
    },
}


def _get_secret() -> str:
    return os.getenv("JWT_SECRET_KEY", "configure-jwt-secret-in-env")


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _encrypt_legacy_xor(key: str, secret: str) -> str:
    data = key.encode("utf-8")
    pad = secret[:32].ljust(32).encode("utf-8")
    encrypted = bytes([data[i] ^ pad[i % 32] for i in range(len(data))])
    return base64.b64encode(encrypted).decode("utf-8")


def _encrypt(key: str, secret: str) -> str:
    aes = AESGCM(_derive_key(secret))
    nonce = secrets.token_bytes(12)
    ciphertext = aes.encrypt(nonce, key.encode("utf-8"), None)
    return "aesgcm:" + base64.b64encode(nonce + ciphertext).decode("utf-8")


def _decrypt(encrypted: str, secret: str) -> str:
    if encrypted.startswith("aesgcm:"):
        raw = base64.b64decode(encrypted[len("aesgcm:") :])
        nonce, ciphertext = raw[:12], raw[12:]
        aes = AESGCM(_derive_key(secret))
        plain = aes.decrypt(nonce, ciphertext, None)
        return plain.decode("utf-8")
    # Backwards-compatible legacy XOR decoding.
    data = base64.b64decode(encrypted)
    pad = secret[:32].ljust(32).encode("utf-8")
    decrypted = bytes([data[i] ^ pad[i % 32] for i in range(len(data))])
    return decrypted.decode("utf-8")


def load_user_keys(email: str) -> list[dict]:
    if not USER_KEYS_FILE.exists():
        return []
    email_l = email.strip().lower()
    with open(USER_KEYS_FILE, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [
        row
        for row in rows
        if str(row.get("user_email", "")).strip().lower() == email_l and not row.get("deleted")
    ]


def save_user_key(key_data: dict) -> None:
    USER_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_KEYS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(key_data, ensure_ascii=False) + "\n")


def rewrite_all_keys(keys: list[dict]) -> None:
    USER_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_KEYS_FILE, "w", encoding="utf-8") as f:
        for item in keys:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _safe_key_rows(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "encrypted_key"} for row in rows]


class AddKeyRequest(BaseModel):
    user_email: Optional[str] = Field(default=None)
    provider: str
    api_key: str = Field(..., min_length=10)
    label: Optional[str] = ""
    base_url: Optional[str] = ""


class UpdateKeyRequest(BaseModel):
    key_id: str
    user_email: Optional[str] = None
    active: bool


@router.get("/providers")
def get_providers() -> dict:
    return {
        "providers": [
            {
                "id": provider_id,
                "name": value["name"],
                "prefix": value["prefix"],
                "models": value["models"],
                "base_url": value["base_url"],
                "icon": value["icon"],
            }
            for provider_id, value in SUPPORTED_PROVIDERS.items()
        ]
    }


@router.get("")
def list_my_user_keys(authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    keys = load_user_keys(email)
    return {"keys": _safe_key_rows(keys), "total": len(keys)}


@router.get("/list/{user_email}")
def list_user_keys_route(user_email: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(user_email, authorization)
    keys = load_user_keys(email)
    return {"keys": _safe_key_rows(keys), "total": len(keys)}


@router.post("/add")
def add_user_key(req: AddKeyRequest, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(req.user_email, authorization)
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail="不支持的提供方")
    existing = load_user_keys(email)
    for row in existing:
        if row["provider"] == req.provider:
            raise HTTPException(status_code=400, detail="该提供方已存在密钥，请先删除后再添加。")
    provider_info = SUPPORTED_PROVIDERS[req.provider]
    encrypted = _encrypt(req.api_key, _get_secret())
    key_data = {
        "key_id": "UK-" + secrets.token_hex(8),
        "user_email": email,
        "provider": req.provider,
        "provider_name": provider_info["name"],
        "label": (req.label or provider_info["name"]).strip(),
        "encrypted_key": encrypted,
        "key_prefix": req.api_key[:8] + "..." + req.api_key[-4:],
        "base_url": (req.base_url or provider_info["base_url"]).strip(),
        "active": True,
        "added_at": datetime.utcnow().isoformat(),
        "last_used": None,
        "usage_count": 0,
    }
    save_user_key(key_data)
    return {
        "message": provider_info["name"] + " 密钥已保存",
        "key_id": key_data["key_id"],
        "provider": req.provider,
    }


@router.post("/toggle")
def toggle_user_key(req: UpdateKeyRequest, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(req.user_email, authorization)
    if not USER_KEYS_FILE.exists():
        raise HTTPException(status_code=404, detail="未找到密钥文件")
    with open(USER_KEYS_FILE, encoding="utf-8") as f:
        all_keys = [json.loads(line) for line in f if line.strip()]
    found = False
    for item in all_keys:
        if item["key_id"] == req.key_id and item["user_email"] == email:
            item["active"] = req.active
            item["updated_at"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="未找到密钥")
    rewrite_all_keys(all_keys)
    return {"message": "密钥状态已更新", "active": req.active}


@router.delete("/delete/{key_id}/{user_email}")
def delete_user_key(key_id: str, user_email: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(user_email, authorization)
    if not USER_KEYS_FILE.exists():
        raise HTTPException(status_code=404, detail="未找到密钥文件")
    with open(USER_KEYS_FILE, encoding="utf-8") as f:
        all_keys = [json.loads(line) for line in f if line.strip()]
    found = False
    for item in all_keys:
        if item["key_id"] == key_id and item["user_email"] == email:
            item["deleted"] = True
            item["deleted_at"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="未找到密钥")
    rewrite_all_keys(all_keys)
    return {"message": "密钥已删除"}


@router.get("/active")
def get_my_active_keys(authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    return _get_active_keys_payload(email)


@router.get("/active/{user_email}")
def get_active_keys(user_email: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(user_email, authorization)
    return _get_active_keys_payload(email)


def _get_active_keys_payload(email: str) -> dict:
    keys = load_user_keys(email)
    active_rows = [row for row in keys if row.get("active")]
    result = {}
    for item in active_rows:
        try:
            decrypted = _decrypt(item["encrypted_key"], _get_secret())
        except Exception:
            continue
        result[item["provider"]] = {
            "api_key": decrypted,
            "base_url": item["base_url"],
            "provider_name": item["provider_name"],
        }
    return {"active_keys": result, "count": len(result)}
