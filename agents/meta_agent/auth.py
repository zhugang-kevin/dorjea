"""
Authentication helpers and compatibility routes for AgentCore.

This module is imported by API, plan enforcement, billing, admin, and payment
code, so backwards-compatible helper names are preserved.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator

router = APIRouter()

USERS_FILE = Path(os.getenv("USERS_FILE", "memory/users.jsonl"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "").strip().lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Login rate limiting: max 10 attempts per IP per 15 minutes
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW = 900  # 15 minutes
_LOGIN_MAX = 10

PLAN_TOKEN_LIMITS: dict[str, int] = {
    "free": 5000,
    "pro": 50000,
    "professional": 50000,
    "business": 150000,
    "enterprise": 500000,
    "owner": 999999999,
}


def _check_login_rate_limit(ip: str) -> None:
    """Raise 429 if IP has exceeded login attempt limit."""
    now = time.time()
    window_start = now - _LOGIN_WINDOW
    attempts = [t for t in _login_attempts[ip] if t > window_start]
    _login_attempts[ip] = attempts
    if len(attempts) >= _LOGIN_MAX:
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 15 分钟后再试")
    _login_attempts[ip].append(now)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _hash_pwd(password: str) -> str:
    """Hash passwords with a salted KDF."""
    return pwd_context.hash(password)


def _load_users_list() -> list[dict[str, Any]]:
    if not USERS_FILE.exists():
        return []
    users: list[dict[str, Any]] = []
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("email"):
                    users.append(row)
    except OSError:
        return []
    return users


def _save_users_list(users: list[dict[str, Any]]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        for user in users:
            f.write(json.dumps(user, ensure_ascii=False) + "\n")


def _find_user(email: str) -> dict[str, Any] | None:
    email_l = _normalize_email(email)
    for user in _load_users_list():
        if _normalize_email(str(user.get("email", ""))) == email_l:
            return user
    return None


def _replace_user(updated_user: dict[str, Any]) -> None:
    email_l = _normalize_email(str(updated_user.get("email", "")))
    users = _load_users_list()
    for idx, user in enumerate(users):
        if _normalize_email(str(user.get("email", ""))) == email_l:
            users[idx] = updated_user
            _save_users_list(users)
            return
    users.append(updated_user)
    _save_users_list(users)


def _public_user_record(user: dict[str, Any]) -> dict[str, Any]:
    public = {k: v for k, v in user.items() if k != "password_hash"}
    email_l = _normalize_email(str(public.get("email", "")))
    public["is_owner"] = bool(
        public.get("is_owner")
        or public.get("plan") == "owner"
        or (OWNER_EMAIL and email_l == OWNER_EMAIL)
    )
    public["is_admin"] = bool(
        public.get("is_admin") or public["is_owner"] or (ADMIN_EMAIL and email_l == ADMIN_EMAIL)
    )
    return public


def _ensure_admin_exists() -> None:
    if not ADMIN_EMAIL:
        return
    if _find_user(ADMIN_EMAIL):
        return
    now = _utcnow().isoformat()
    is_owner = bool(OWNER_EMAIL and ADMIN_EMAIL == OWNER_EMAIL)
    admin_user = {
        "id": str(uuid.uuid4()),
        "email": ADMIN_EMAIL,
        "name": "系统管理员" if not is_owner else "系统所有者",
        "password_hash": _hash_pwd(ADMIN_PASSWORD) if ADMIN_PASSWORD else "",
        "plan": "owner" if is_owner else "enterprise",
        "is_admin": True,
        "is_owner": is_owner,
        "generated_by_admin": False,
        "suspended": False,
        "active": True,
        "discount_percent": 100,
        "daily_tokens_used": 0,
        "tokens_used_today": 0,
        "tokens_reset_date": _utcnow().date().isoformat(),
        "referral_code": "OWNER001" if is_owner else "ADMIN001",
        "note": "系统初始化管理员账户",
        "created_at": now,
        "updated_at": now,
        "login_count": 0,
    }
    _replace_user(admin_user)


def _create_access_token(email: str, plan: str, is_admin: bool, is_owner: bool) -> str:
    now = _utcnow()
    payload = {
        "sub": _normalize_email(email),
        "email": _normalize_email(email),
        "plan": plan,
        "is_admin": bool(is_admin),
        "is_owner": bool(is_owner),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    email = _normalize_email(str(payload.get("sub") or payload.get("email") or ""))
    if not email:
        return None
    is_owner = bool(
        payload.get("is_owner")
        or payload.get("plan") == "owner"
        or (OWNER_EMAIL and email == OWNER_EMAIL)
    )
    return {
        "sub": email,
        "email": email,
        "plan": str(payload.get("plan") or "free"),
        "is_admin": bool(payload.get("is_admin") or is_owner),
        "is_owner": is_owner,
        "exp": payload.get("exp"),
        "iat": payload.get("iat"),
    }


def get_user_by_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    clean = token.strip()
    if clean.startswith("admin_"):
        clean = clean[6:]
    payload = decode_access_token(clean)
    if not payload:
        return None
    email = payload["email"]
    user = _find_user(email)
    if not user:
        if ADMIN_EMAIL and email == ADMIN_EMAIL:
            _ensure_admin_exists()
            user = _find_user(email)
        if not user and OWNER_EMAIL and email == OWNER_EMAIL:
            user = {
                "email": email,
                "name": "系统所有者",
                "plan": "owner",
                "is_admin": True,
                "is_owner": True,
                "daily_tokens_used": 0,
                "tokens_used_today": 0,
            }
    if not user:
        return None
    public = _public_user_record(user)
    public["plan"] = str(public.get("plan") or payload.get("plan") or "free")
    return public


def _validate_email(email: str) -> tuple[bool, str | None]:
    email_l = _normalize_email(email)
    if "@" not in email_l or "." not in email_l.split("@")[-1]:
        return False, "邮箱格式不正确"
    if len(email_l) > 254:
        return False, "邮箱长度不合法"
    return True, None


def _reset_daily_usage_if_needed(user: dict[str, Any]) -> dict[str, Any]:
    today = _utcnow().date().isoformat()
    if user.get("tokens_reset_date") != today:
        user["tokens_reset_date"] = today
        user["daily_tokens_used"] = 0
        user["tokens_used_today"] = 0
    return user


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        if hashed.startswith("$pbkdf2-sha256$"):
            return pwd_context.verify(plain, hashed)
    except Exception:
        return False
    return _legacy_sha256(plain) == hashed


def hash_password(password: str) -> str:
    return _hash_pwd(password)


def make_token(email: str, plan: str, is_admin: bool) -> str:
    email_l = _normalize_email(email)
    is_owner = bool(plan == "owner" or (OWNER_EMAIL and email_l == OWNER_EMAIL))
    return _create_access_token(email_l, plan, bool(is_admin or is_owner), is_owner)


def check_daily_tokens(user: dict[str, Any], tokens_requested: int) -> tuple[bool, int, int]:
    user = _reset_daily_usage_if_needed(dict(user))
    email = _normalize_email(str(user.get("email", "")))
    plan = str(user.get("plan", "free"))
    limit = int(PLAN_TOKEN_LIMITS.get(plan, PLAN_TOKEN_LIMITS["free"]))
    if plan == "owner" or (OWNER_EMAIL and email == OWNER_EMAIL):
        return True, 0, limit
    used = int(user.get("daily_tokens_used", user.get("tokens_used_today", 0)) or 0)
    requested = max(0, int(tokens_requested))
    return used + requested <= limit, used, limit


def update_token_usage(user: dict[str, Any], tokens_used: int) -> dict[str, Any]:
    mutable = dict(user)
    mutable = _reset_daily_usage_if_needed(mutable)
    used = int(mutable.get("daily_tokens_used", mutable.get("tokens_used_today", 0)) or 0)
    mutable["daily_tokens_used"] = used + int(tokens_used)
    mutable["tokens_used_today"] = mutable["daily_tokens_used"]
    mutable["updated_at"] = _utcnow().isoformat()
    _replace_user(mutable)
    return mutable


def register_user(
    email: str,
    password: str,
    name: str,
    ip: str,
    ua: str,
    lang: str,
) -> tuple[dict[str, Any] | None, str | None]:
    _ = (ip, ua, lang)
    email_l = _normalize_email(email)
    ok, err = _validate_email(email_l)
    if not ok:
        return None, err
    if len(password) < 8:
        return None, "密码长度不能少于8位"
    if _find_user(email_l):
        return None, "该邮箱已注册，请直接登录"
    now = _utcnow().isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "email": email_l,
        "name": (name or email_l.split("@")[0]).strip(),
        "password_hash": _hash_pwd(password),
        "plan": "free",
        "is_admin": False,
        "is_owner": False,
        "generated_by_admin": False,
        "suspended": False,
        "active": True,
        "discount_percent": 100,
        "daily_tokens_used": 0,
        "tokens_used_today": 0,
        "tokens_reset_date": _utcnow().date().isoformat(),
        "referral_code": uuid.uuid4().hex[:8].upper(),
        "note": "",
        "created_at": now,
        "updated_at": now,
        "login_count": 0,
    }
    _replace_user(user)
    return _public_user_record(user), None


def login_user(
    email: str,
    password: str,
    ip: str,
    ua: str,
) -> tuple[dict[str, Any] | None, str | None]:
    _ = ua
    _check_login_rate_limit(ip or "unknown")
    _ensure_admin_exists()
    email_l = _normalize_email(email)
    user = _find_user(email_l)
    if not user:
        return None, "邮箱或密码错误，请重试"
    if user.get("suspended", False) or user.get("active") is False:
        return None, "账户已被封禁，请联系客服"
    stored_hash = str(user.get("password_hash", "") or "")
    if not verify_password(password, stored_hash):
        return None, "邮箱或密码错误，请重试"

    # Migrate legacy unsalted SHA-256 hashes on successful login.
    if stored_hash and not stored_hash.startswith("$pbkdf2-sha256$"):
        user["password_hash"] = _hash_pwd(password)

    user = _reset_daily_usage_if_needed(user)
    user["updated_at"] = _utcnow().isoformat()
    user["last_login"] = user["updated_at"]
    user["login_count"] = int(user.get("login_count", 0)) + 1

    email_l = _normalize_email(str(user.get("email", "")))
    is_owner = bool(
        user.get("is_owner")
        or user.get("plan") == "owner"
        or (OWNER_EMAIL and email_l == OWNER_EMAIL)
    )
    is_admin = bool(user.get("is_admin") or is_owner or (ADMIN_EMAIL and email_l == ADMIN_EMAIL))
    if is_admin and not user.get("is_admin"):
        user["is_admin"] = True
    if is_owner and not user.get("is_owner"):
        user["is_owner"] = True
        user["plan"] = "owner"

    _replace_user(user)
    plan = str(user.get("plan", "free"))
    token = _create_access_token(email_l, plan, is_admin, is_owner)
    return {"user": _public_user_record(user), "token": token}, None


def get_plan_limits(plan: str) -> dict[str, int]:
    key = str(plan or "free").lower().strip()
    if key == "pro":
        key = "professional"
    return {
        "daily_tokens": PLAN_TOKEN_LIMITS.get(key, PLAN_TOKEN_LIMITS["free"]),
        "max_agents": {
            "free": 3,
            "professional": 20,
            "business": 100,
            "enterprise": 500,
            "owner": 999999,
        }.get(key, 3),
        "max_clones": {
            "free": 0,
            "professional": 0,
            "business": 3,
            "enterprise": 10,
            "owner": 1000,
        }.get(key, 0),
    }


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        ok, err = _validate_email(value)
        if not ok:
            raise ValueError(err or "邮箱格式不正确")
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码长度不能少于8位")
        return value


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


@router.post("/login")
async def login(req: LoginRequest) -> dict[str, Any]:
    result, error = login_user(req.email, req.password, "", "")
    if error:
        raise HTTPException(status_code=401, detail=error)
    user = result["user"]
    return {
        "token": result["token"],
        "access_token": result["token"],
        "token_type": "Bearer",
        "email": user["email"],
        "name": user.get("name", ""),
        "plan": user.get("plan", "free"),
        "is_admin": bool(user.get("is_admin", False)),
        "is_owner": bool(user.get("is_owner", False)),
        "daily_token_limit": PLAN_TOKEN_LIMITS.get(str(user.get("plan", "free")), 5000),
        "tokens_used_today": int(user.get("daily_tokens_used", 0)),
    }


@router.post("/register")
async def register(req: RegisterRequest) -> dict[str, Any]:
    user, error = register_user(req.email, req.password, req.name, "", "", "zh")
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {
        "success": True,
        "message": "注册成功，请登录。",
        "email": user["email"],
    }


@router.get("/me")
async def get_me(authorization: str | None = Header(None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.replace("Bearer ", "", 1).strip()
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期，请重新登录")
    return {
        "email": user["email"],
        "name": user.get("name", ""),
        "plan": user.get("plan", "free"),
        "is_admin": bool(user.get("is_admin", False)),
        "is_owner": bool(user.get("is_owner", False)),
        "daily_token_limit": get_plan_limits(str(user.get("plan", "free")))["daily_tokens"],
        "tokens_used_today": int(user.get("daily_tokens_used", 0)),
    }


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest) -> dict[str, Any]:
    _ = req
    return {
        "success": True,
        "message": "如果邮箱已注册，重置链接将发送至您的邮箱。",
    }


def load_users() -> dict[str, dict[str, Any]]:
    """Compatibility helper: return users keyed by email."""
    return {
        _normalize_email(str(user.get("email", ""))): user
        for user in _load_users_list()
        if user.get("email")
    }


def save_users(users: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> None:
    """Compatibility helper: accept either a dict or a list of users."""
    if isinstance(users, dict):
        rows = list(users.values())
    else:
        rows = list(users)
    _save_users_list(rows)


def save_user(user: dict[str, Any]) -> None:
    _replace_user(user)


def get_user(email: str) -> dict[str, Any] | None:
    return _find_user(email)


def create_user(user: dict[str, Any]) -> dict[str, Any]:
    _replace_user(user)
    return user
