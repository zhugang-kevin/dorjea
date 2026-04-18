import os
import json
import base64
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/user-keys", tags=["User API Keys"])
USER_KEYS_FILE = "memory/user_api_keys.jsonl"

SUPPORTED_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic Claude",
        "prefix": "sk-ant",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
        "base_url": "https://api.anthropic.com",
        "icon": "🤖",
    },
    "openai": {
        "name": "OpenAI",
        "prefix": "sk-",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1",
        "icon": "🟢",
    },
    "google": {
        "name": "Google AI Studio",
        "prefix": "AIza",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro"],
        "base_url": "https://generativelanguage.googleapis.com",
        "icon": "🔵",
    },
    "deepseek": {
        "name": "DeepSeek",
        "prefix": "sk-",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": "https://api.deepseek.com",
        "icon": "🌊",
    },
    "groq": {
        "name": "Groq",
        "prefix": "gsk_",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "base_url": "https://api.groq.com/openai/v1",
        "icon": "⚡",
    },
    "mistral": {
        "name": "Mistral AI",
        "prefix": "",
        "models": ["mistral-large-latest", "mistral-medium-latest"],
        "base_url": "https://api.mistral.ai/v1",
        "icon": "🌀",
    },
    "azure": {
        "name": "Microsoft Azure OpenAI",
        "prefix": "",
        "models": ["gpt-4o", "gpt-4-turbo"],
        "base_url": "https://your-resource.openai.azure.com",
        "icon": "🔷",
    },
}

def _encrypt(key: str, secret: str) -> str:
    data = key.encode()
    pad = secret[:32].ljust(32).encode()
    encrypted = bytes([data[i] ^ pad[i % 32] for i in range(len(data))])
    return base64.b64encode(encrypted).decode()

def _decrypt(encrypted: str, secret: str) -> str:
    data = base64.b64decode(encrypted)
    pad = secret[:32].ljust(32).encode()
    decrypted = bytes([data[i] ^ pad[i % 32] for i in range(len(data))])
    return decrypted.decode()

def _get_secret():
    return os.getenv("JWT_SECRET_KEY", "dorjea-default-secret-key-2026")

def load_user_keys(email: str):
    if not os.path.exists(USER_KEYS_FILE):
        return []
    with open(USER_KEYS_FILE, encoding="utf-8") as f:
        all_keys = [json.loads(l) for l in f if l.strip()]
    return [k for k in all_keys if k["user_email"] == email and not k.get("deleted")]

def save_user_key(key_data):
    with open(USER_KEYS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(key_data) + "\n")

def rewrite_all_keys(keys):
    with open(USER_KEYS_FILE, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(json.dumps(k) + "\n")

class AddKeyRequest(BaseModel):
    user_email: str
    provider: str
    api_key: str
    label: Optional[str] = ""
    base_url: Optional[str] = ""

class UpdateKeyRequest(BaseModel):
    key_id: str
    user_email: str
    active: bool

@router.get("/providers")
def get_providers():
    return {"providers": [
        {"id": k, "name": v["name"], "prefix": v["prefix"],
         "models": v["models"], "base_url": v["base_url"], "icon": v["icon"]}
        for k, v in SUPPORTED_PROVIDERS.items()
    ]}

@router.post("/add")
def add_user_key(req: AddKeyRequest):
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(400, detail="Unsupported provider")
    if len(req.api_key) < 10:
        raise HTTPException(400, detail="API key is too short")
    existing = load_user_keys(req.user_email)
    for k in existing:
        if k["provider"] == req.provider:
            raise HTTPException(400, detail=f"You already have a {req.provider} key. Delete it first to add a new one.")
    provider_info = SUPPORTED_PROVIDERS[req.provider]
    encrypted = _encrypt(req.api_key, _get_secret())
    key_data = {
        "key_id": "UK-" + secrets.token_hex(8),
        "user_email": req.user_email,
        "provider": req.provider,
        "provider_name": provider_info["name"],
        "label": req.label or provider_info["name"],
        "encrypted_key": encrypted,
        "key_prefix": req.api_key[:8] + "..." + req.api_key[-4:],
        "base_url": req.base_url or provider_info["base_url"],
        "active": True,
        "added_at": datetime.utcnow().isoformat(),
        "last_used": None,
        "usage_count": 0,
    }
    save_user_key(key_data)
    return {"message": f"{provider_info['name']} key added successfully",
            "key_id": key_data["key_id"],
            "provider": req.provider}

@router.get("/list/{user_email}")
def list_user_keys(user_email: str):
    keys = load_user_keys(user_email)
    safe_keys = [{k: v for k, v in key.items() if k != "encrypted_key"}
                 for key in keys]
    return {"keys": safe_keys, "total": len(safe_keys)}

@router.post("/toggle")
def toggle_user_key(req: UpdateKeyRequest):
    if not os.path.exists(USER_KEYS_FILE):
        raise HTTPException(404, detail="Key not found")
    with open(USER_KEYS_FILE, encoding="utf-8") as f:
        all_keys = [json.loads(l) for l in f if l.strip()]
    found = False
    for k in all_keys:
        if k["key_id"] == req.key_id and k["user_email"] == req.user_email:
            k["active"] = req.active
            found = True
            break
    if not found:
        raise HTTPException(404, detail="Key not found")
    rewrite_all_keys(all_keys)
    return {"message": "Key updated", "active": req.active}

@router.delete("/delete/{key_id}/{user_email}")
def delete_user_key(key_id: str, user_email: str):
    if not os.path.exists(USER_KEYS_FILE):
        raise HTTPException(404, detail="Key not found")
    with open(USER_KEYS_FILE, encoding="utf-8") as f:
        all_keys = [json.loads(l) for l in f if l.strip()]
    found = False
    for k in all_keys:
        if k["key_id"] == key_id and k["user_email"] == user_email:
            k["deleted"] = True
            found = True
            break
    if not found:
        raise HTTPException(404, detail="Key not found")
    rewrite_all_keys(all_keys)
    return {"message": "Key deleted successfully"}

@router.get("/active/{user_email}")
def get_active_keys(user_email: str):
    keys = load_user_keys(user_email)
    active = [k for k in keys if k.get("active")]
    result = {}
    for k in active:
        try:
            decrypted = _decrypt(k["encrypted_key"], _get_secret())
            result[k["provider"]] = {
                "api_key": decrypted,
                "base_url": k["base_url"],
                "provider_name": k["provider_name"],
            }
        except Exception:
            pass
    return {"active_keys": result, "count": len(result)}