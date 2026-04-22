import secrets
import hashlib
import json
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from agents.meta_agent.plan_enforcement import require_feature, resolve_scoped_user_email
from pydantic import BaseModel

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"],
    dependencies=[Depends(require_feature("api_keys"))],
)
KEYS_FILE = "memory/api_keys.jsonl"

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return []
    with open(KEYS_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def save_key(key_data):
    with open(KEYS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(key_data) + "\n")

def rewrite_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(json.dumps(k) + "\n")

class CreateKeyRequest(BaseModel):
    user_email: Optional[str] = None
    name: str
    permissions: list = ["read", "write"]

class RevokeKeyRequest(BaseModel):
    user_email: Optional[str] = None
    key_id: str

@router.post("/create")
def create_api_key(req: CreateKeyRequest, authorization: str | None = Header(None)):
    user_email = resolve_scoped_user_email(req.user_email, authorization)
    raw_key = "dj_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    keys = load_keys()
    user_keys = [k for k in keys if k["user_email"] == user_email and not k.get("revoked")]
    if len(user_keys) >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 API keys per account")
    key_data = {
        "key_id": "kid_" + secrets.token_hex(8),
        "user_email": user_email,
        "name": req.name,
        "key_hash": key_hash,
        "key_prefix": raw_key[:12] + "...",
        "permissions": req.permissions,
        "created_at": datetime.utcnow().isoformat(),
        "last_used": None,
        "usage_count": 0,
        "revoked": False,
    }
    save_key(key_data)
    return {"key": raw_key, "key_id": key_data["key_id"], "name": req.name,
            "prefix": key_data["key_prefix"], "created_at": key_data["created_at"],
            "message": "Copy this key now. It will never be shown again."}

@router.get("/list/{user_email}")
def list_api_keys(user_email: str, authorization: str | None = Header(None)):
    scoped_email = resolve_scoped_user_email(user_email, authorization)
    keys = load_keys()
    user_keys = [
        {k: v for k, v in key.items() if k != "key_hash"}
        for key in keys
        if key["user_email"] == scoped_email and not key.get("revoked")
    ]
    return {"keys": user_keys, "total": len(user_keys)}

@router.post("/revoke")
def revoke_api_key(req: RevokeKeyRequest, authorization: str | None = Header(None)):
    user_email = resolve_scoped_user_email(req.user_email, authorization)
    keys = load_keys()
    found = False
    for k in keys:
        if k["key_id"] == req.key_id and k["user_email"] == user_email:
            k["revoked"] = True
            k["revoked_at"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Key not found")
    rewrite_keys(keys)
    return {"message": "API key revoked successfully"}

@router.post("/verify")
def verify_api_key(authorization: str = Header(...)):
    if not authorization.startswith("Bearer dj_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    raw_key = authorization.replace("Bearer ", "")
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    keys = load_keys()
    for k in keys:
        if k["key_hash"] == key_hash and not k.get("revoked"):
            k["last_used"] = datetime.utcnow().isoformat()
            k["usage_count"] = k.get("usage_count", 0) + 1
            rewrite_keys(keys)
            return {"valid": True, "user_email": k["user_email"],
                    "permissions": k["permissions"], "name": k["name"]}
    raise HTTPException(status_code=401, detail="Invalid or revoked API key")

@router.get("/docs")
def api_docs():
    return {
        "base_url": "https://api.dorjea.com",
        "version": "v1",
        "authentication": "Bearer token in Authorization header",
        "key_format": "dj_xxxxx",
        "endpoints": {
            "GET /agents": "List all your agents",
            "POST /agents/create": "Create a new agent",
            "POST /agents/{name}/run": "Run a task on an agent",
            "GET /agents/{name}": "Get agent details",
            "GET /system/budget": "Get token budget status",
            "GET /audit": "Get audit log",
            "GET /health": "System health check",
        },
        "example": {
            "curl": "curl -H \"Authorization: Bearer dj_your_key_here\" https://api.dorjea.com/agents",
            "python": "import requests\nres = requests.get(\"https://api.dorjea.com/agents\", headers={\"Authorization\": \"Bearer dj_your_key_here\"})"
        }
    }
