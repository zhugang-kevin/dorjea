import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path
from jose import jwt, JWTError
import hmac

SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
USERS_DB = Path("memory/users.jsonl")
SESSIONS_DB = Path("memory/sessions.jsonl")

ALLOWED_EMAIL_DOMAINS = [
    "gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com",
    "qq.com","163.com","126.com","sina.com","sohu.com","foxmail.com",
    "yeah.net","189.cn","139.com","wo.cn",
]

PLAN_LIMITS = {
    "free":         {"daily_tokens": 10000,  "max_agents": 3,   "max_clones": 0, "price_usd": 0,   "price_cny": 0},
    "professional": {"daily_tokens": 100000, "max_agents": 20,  "max_clones": 1, "price_usd": 49,  "price_cny": 349},
    "business":     {"daily_tokens": 500000, "max_agents": 100, "max_clones": 5, "price_usd": 199, "price_cny": 1399},
    "enterprise":   {"daily_tokens": 999999, "max_agents": 999, "max_clones": 99,"price_usd": 999, "price_cny": 6999},
}


def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password[:72]).encode()).hexdigest()
    return salt + ":" + h


def verify_password(plain, hashed):
    try:
        salt, h = hashed.split(":", 1)
        return hmac.compare_digest(h, hashlib.sha256((salt + plain[:72]).encode()).hexdigest())
    except Exception:
        return False


def create_access_token(data: dict, expires_hours=ACCESS_TOKEN_EXPIRE_HOURS):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_device_fingerprint(user_agent: str, ip: str):
    raw = user_agent + "|" + ip.split(".")[0] + "." + ip.split(".")[1]
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def validate_email(email: str):
    email = email.lower().strip()
    if "@" not in email:
        return False, "Invalid email format"
    domain = email.split("@")[1]
    parts = domain.split(".")
    if len(parts) < 2:
        return False, "Invalid email domain"
    if len(email) > 254:
        return False, "Email too long"
    return True, ""


def load_users():
    if not USERS_DB.exists():
        return {}
    users = {}
    try:
        with open(USERS_DB, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    u = json.loads(line)
                    users[u["email"]] = u
    except Exception:
        pass
    return users


def save_user(user: dict):
    USERS_DB.parent.mkdir(parents=True, exist_ok=True)
    users = load_users()
    users[user["email"]] = user
    with open(USERS_DB, "w", encoding="utf-8") as f:
        for u in users.values():
            f.write(json.dumps(u) + chr(10))


def register_user(email, password, name, ip="", user_agent="", lang="en"):
    email = email.lower().strip()
    valid, err = validate_email(email)
    if not valid:
        return None, err
    users = load_users()
    if email in users:
        return None, "Email already registered"
    if len(password) < 8:
        return None, "Password must be at least 8 characters"
    device_fp = get_device_fingerprint(user_agent, ip)
    user = {
        "id": secrets.token_hex(16),
        "email": email,
        "name": name,
        "password_hash": hash_password(password),
        "plan": "free",
        "lang": lang,
        "device_fingerprints": [device_fp],
        "daily_tokens_used": 0,
        "tokens_reset_date": datetime.utcnow().date().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
        "login_count": 0,
    }
    save_user(user)
    return user, None


def login_user(email, password, ip="", user_agent=""):
    email = email.lower().strip()
    users = load_users()
    user = users.get(email)
    if not user:
        return None, "Invalid email or password"
    if not verify_password(password, user["password_hash"]):
        return None, "Invalid email or password"
    if not user.get("active", True):
        return None, "Account suspended"
    device_fp = get_device_fingerprint(user_agent, ip)
    known_devices = user.get("device_fingerprints", [])
    if device_fp not in known_devices:
        if len(known_devices) >= 3:
            return None, "Too many devices. Please contact support to add a new device."
        known_devices.append(device_fp)
        user["device_fingerprints"] = known_devices
    user["login_count"] = user.get("login_count", 0) + 1
    user["last_login"] = datetime.utcnow().isoformat()
    save_user(user)
    token = create_access_token({"sub": email, "user_id": user["id"], "plan": user["plan"]})
    return {"token": token, "user": {k: v for k, v in user.items() if k != "password_hash"}}, None


def get_user_by_token(token: str):
    payload = decode_access_token(token)
    if not payload:
        return None
    email = payload.get("sub")
    if not email:
        return None
    users = load_users()
    return users.get(email)


def get_plan_limits(plan: str):
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


def check_daily_tokens(user: dict, tokens_to_use: int):
    today = datetime.utcnow().date().isoformat()
    if user.get("tokens_reset_date") != today:
        user["daily_tokens_used"] = 0
        user["tokens_reset_date"] = today
        save_user(user)
    limits = get_plan_limits(user.get("plan", "free"))
    used = user.get("daily_tokens_used", 0)
    if used + tokens_to_use > limits["daily_tokens"]:
        return False, used, limits["daily_tokens"]
    return True, used, limits["daily_tokens"]


def update_token_usage(user: dict, tokens_used: int):
    today = datetime.utcnow().date().isoformat()
    if user.get("tokens_reset_date") != today:
        user["daily_tokens_used"] = 0
        user["tokens_reset_date"] = today
    user["daily_tokens_used"] = user.get("daily_tokens_used", 0) + tokens_used
    save_user(user)