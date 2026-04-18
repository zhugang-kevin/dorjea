import os

CONTENT = '''\
from __future__ import annotations
import json
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth Extended"])

# ── file paths ─────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USERS_FILE  = os.path.join(_BASE, "memory", "users.jsonl")
TOKENS_FILE = os.path.join(_BASE, "memory", "auth_tokens.jsonl")

# ── SMTP config ────────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_NAME = "Dorjea AI"


# ── helpers ────────────────────────────────────────────────────────────────

def _ensure_dir(path: str) -> None:
    """Create parent directory if it does not exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _read_jsonl(path: str) -> list[dict]:
    """Read all records from a .jsonl file."""
    if not os.path.exists(path):
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _write_jsonl(path: str, records: list[dict]) -> None:
    """Overwrite a .jsonl file with the given records."""
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\\n")


def _append_jsonl(path: str, record: dict) -> None:
    """Append a single record to a .jsonl file."""
    _ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\n")


def load_user(email: str) -> Optional[dict]:
    """Return the user record matching email, or None."""
    for rec in _read_jsonl(USERS_FILE):
        if rec.get("email", "").lower() == email.lower():
            return rec
    return None


def rewrite_users(users: list[dict]) -> None:
    """Overwrite users.jsonl with the provided list."""
    _write_jsonl(USERS_FILE, users)


def save_token(token_data: dict) -> None:
    """Append a token record to auth_tokens.jsonl."""
    _append_jsonl(TOKENS_FILE, token_data)


def load_token(token: str, token_type: str) -> Optional[dict]:
    """Find the most recent unused token matching value and type."""
    matches = [
        r for r in _read_jsonl(TOKENS_FILE)
        if r.get("token") == token
        and r.get("type") == token_type
        and not r.get("used", False)
    ]
    return matches[-1] if matches else None


def load_token_by_code(email: str, code: str, token_type: str) -> Optional[dict]:
    """Find an unused token matching email, code, and type."""
    matches = [
        r for r in _read_jsonl(TOKENS_FILE)
        if r.get("email", "").lower() == email.lower()
        and r.get("code") == code
        and r.get("type") == token_type
        and not r.get("used", False)
    ]
    return matches[-1] if matches else None


def invalidate_token(token_id: str) -> None:
    """Mark a token as used by its token_id."""
    records = _read_jsonl(TOKENS_FILE)
    for rec in records:
        if rec.get("token_id") == token_id:
            rec["used"] = True
            break
    _write_jsonl(TOKENS_FILE, records)


def send_auth_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP. Returns True on success."""
    if not SMTP_USER or not SMTP_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception:
        return False


def _verification_html(code: str) -> str:
    """Return branded HTML email for email verification."""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#1e293b;border-radius:12px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#38bdf8,#818cf8);padding:28px 36px;">
          <h1 style="margin:0;color:#fff;font-size:24px;font-weight:800;">🤖 Dorjea AI</h1>
          <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">Verify your account</p>
        </td></tr>
        <tr><td style="padding:36px;">
          <p style="color:#94a3b8;font-size:15px;margin:0 0 24px;">Enter this 6-digit code to verify your Dorjea account:</p>
          <div style="background:#0f172a;border:2px solid #38bdf8;border-radius:10px;padding:24px;text-align:center;margin-bottom:24px;">
            <span style="font-size:42px;font-weight:900;letter-spacing:12px;color:#38bdf8;">{code}</span>
          </div>
          <p style="color:#64748b;font-size:13px;margin:0;">This code expires in <strong style="color:#94a3b8;">30 minutes</strong>. If you did not request this, you can safely ignore this email.</p>
        </td></tr>
        <tr><td style="padding:20px 36px;border-top:1px solid #334155;">
          <p style="color:#475569;font-size:12px;margin:0;">© {datetime.utcnow().year} Dorjea AI · Automated message, do not reply</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _reset_html(reset_url: str) -> str:
    """Return branded HTML email for password reset."""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#1e293b;border-radius:12px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#38bdf8,#818cf8);padding:28px 36px;">
          <h1 style="margin:0;color:#fff;font-size:24px;font-weight:800;">🤖 Dorjea AI</h1>
          <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">Password reset request</p>
        </td></tr>
        <tr><td style="padding:36px;">
          <p style="color:#94a3b8;font-size:15px;margin:0 0 24px;">We received a request to reset your Dorjea password. Click the button below to choose a new password:</p>
          <div style="text-align:center;margin-bottom:28px;">
            <a href="{reset_url}" style="display:inline-block;background:linear-gradient(135deg,#38bdf8,#818cf8);color:#fff;text-decoration:none;padding:14px 36px;border-radius:8px;font-weight:700;font-size:15px;">Reset Password</a>
          </div>
          <p style="color:#64748b;font-size:13px;margin:0 0 8px;">Or copy this link into your browser:</p>
          <p style="color:#38bdf8;font-size:12px;word-break:break-all;margin:0;">{reset_url}</p>
          <p style="color:#64748b;font-size:13px;margin:16px 0 0;">This link expires in <strong style="color:#94a3b8;">1 hour</strong>. If you did not request a password reset, you can safely ignore this email.</p>
        </td></tr>
        <tr><td style="padding:20px 36px;border-top:1px solid #334155;">
          <p style="color:#475569;font-size:12px;margin:0;">© {datetime.utcnow().year} Dorjea AI · Automated message, do not reply</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── request models ─────────────────────────────────────────────────────────

class EmailRequest(BaseModel):
    """Request carrying only an email address."""
    email: str


class VerifyEmailRequest(BaseModel):
    """Request to verify an email with a 6-digit code."""
    email: str
    code: str


class PasswordResetRequest(BaseModel):
    """Request to complete a password reset."""
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Request to change password while authenticated."""
    email: str
    current_password: str
    new_password: str


# ── endpoints ──────────────────────────────────────────────────────────────

@router.post("/send-verification")
def send_verification(body: EmailRequest) -> dict:
    """Send a 6-digit email verification code to the user."""
    user = load_user(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email address.")
    if user.get("email_verified", False):
        return {"message": "Email is already verified.", "email": body.email}

    code = str(secrets.randbelow(900000) + 100000)
    now  = datetime.utcnow()
    token_record = {
        "token_id":   secrets.token_hex(8),
        "email":      body.email,
        "code":       code,
        "token":      code,
        "type":       "email_verification",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
        "used":       False,
    }
    save_token(token_record)
    send_auth_email(body.email, "Verify your Dorjea account", _verification_html(code))
    return {"message": "Verification email sent.", "email": body.email}


@router.post("/verify-email")
def verify_email(body: VerifyEmailRequest) -> dict:
    """Verify a user\'s email address using the 6-digit code."""
    token_rec = load_token_by_code(body.email, body.code, "email_verification")
    if not token_rec:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    expires_at = datetime.fromisoformat(token_rec["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    users = _read_jsonl(USERS_FILE)
    updated = False
    for u in users:
        if u.get("email", "").lower() == body.email.lower():
            u["email_verified"] = True
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")

    rewrite_users(users)
    invalidate_token(token_rec["token_id"])
    return {"message": "Email verified successfully.", "verified": True}


@router.post("/send-password-reset")
def send_password_reset(body: EmailRequest) -> dict:
    """Send a password reset link to the user\'s email."""
    user = load_user(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email address.")

    reset_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    token_record = {
        "token_id":   secrets.token_hex(8),
        "email":      body.email,
        "token":      reset_token,
        "code":       "",
        "type":       "password_reset",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "used":       False,
    }
    save_token(token_record)

    app_url  = os.getenv("APP_URL", "http://localhost:3000")
    reset_url = f"{app_url}/reset-password?token={reset_token}"
    send_auth_email(body.email, "Reset your Dorjea password", _reset_html(reset_url))
    return {"message": "Password reset email sent.", "email": body.email}


@router.post("/reset-password")
def reset_password(body: PasswordResetRequest) -> dict:
    """Complete a password reset using the token from the email link."""
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    token_rec = load_token(body.token, "password_reset")
    if not token_rec:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    expires_at = datetime.fromisoformat(token_rec["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    import hashlib
    new_hash = hashlib.sha256(body.new_password.encode()).hexdigest()
    users = _read_jsonl(USERS_FILE)
    updated = False
    for u in users:
        if u.get("email", "").lower() == token_rec["email"].lower():
            u["password_hash"] = new_hash
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")

    rewrite_users(users)
    invalidate_token(token_rec["token_id"])
    return {"message": "Password reset successfully. You can now log in with your new password."}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest) -> dict:
    """Change password for an authenticated user who knows their current password."""
    import hashlib
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    user = load_user(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    current_hash = hashlib.sha256(body.current_password.encode()).hexdigest()
    if user.get("password_hash") != current_hash:
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    new_hash = hashlib.sha256(body.new_password.encode()).hexdigest()
    users = _read_jsonl(USERS_FILE)
    for u in users:
        if u.get("email", "").lower() == body.email.lower():
            u["password_hash"] = new_hash
            break
    rewrite_users(users)
    return {"message": "Password changed successfully."}


@router.get("/verification-status/{email}")
def verification_status(email: str) -> dict:
    """Return whether a user\'s email is verified."""
    user = load_user(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "email":          user["email"],
        "email_verified": user.get("email_verified", False),
    }
'''

dest = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agents", "meta_agent", "auth_extended.py"
)
with open(dest, "w", encoding="utf-8") as f:
    f.write(CONTENT)
print(f"Written {len(CONTENT)} chars to {dest}")
