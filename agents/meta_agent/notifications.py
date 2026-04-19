import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/notifications", tags=["Notifications"])

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@dorjea.com")
FROM_NAME = os.getenv("FROM_NAME", "Dorjea AI Factory")

NOTIFICATIONS_FILE = "memory/notifications.jsonl"

def save_notification(record):
    with open(NOTIFICATIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EMAIL SKIPPED - no SMTP config] To: {to_email} | Subject: {subject}")
        save_notification({
            "to": to_email, "subject": subject,
            "status": "skipped_no_smtp",
            "timestamp": datetime.utcnow().isoformat()
        })
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() == 'true'
        if use_ssl:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        save_notification({
            "to": to_email, "subject": subject,
            "status": "sent",
            "timestamp": datetime.utcnow().isoformat()
        })
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        save_notification({
            "to": to_email, "subject": subject,
            "status": "failed", "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })
        return False

def _base_template(content: str, title: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#f8f6f1;font-family:system-ui,-apple-system,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:40px 20px;">
    <div style="text-align:center;margin-bottom:32px;">
      <h1 style="color:#2563eb;font-size:28px;font-weight:900;margin:0;">Dorjea</h1>
      <p style="color:#6b6b80;font-size:13px;margin:4px 0 0;">AI Agent Factory</p>
    </div>
    <div style="background:#ffffff;border-radius:16px;padding:40px;border:1px solid #e5e0d8;">
      {content}
    </div>
    <div style="text-align:center;margin-top:24px;font-size:12px;color:#6b6b80;">
      <p>Dorjea AI Factory &nbsp;|&nbsp;
         <a href="https://dorjea.com" style="color:#2563eb;">dorjea.com</a> &nbsp;|&nbsp;
         <a href="https://dorjea.com/terms" style="color:#6b6b80;">Terms</a> &nbsp;|&nbsp;
         <a href="https://dorjea.com/privacy" style="color:#6b6b80;">Privacy</a>
      </p>
    </div>
  </div>
</body>
</html>"""

def send_welcome_email(to_email: str, name: str, plan: str) -> bool:
    content = f"""
      <h2 style="color:#1a1a2e;font-size:24px;margin:0 0 16px;">Welcome to Dorjea, {name}! 🎉</h2>
      <p style="color:#6b6b80;line-height:1.7;margin:0 0 20px;">
        Your account is ready. You are on the <strong style="color:#2563eb;">{plan.title()} plan</strong>
        {"with a 3-day free trial" if plan == "free" else ""}.
      </p>
      <h3 style="color:#1a1a2e;font-size:16px;margin:0 0 12px;">Get started in 3 steps:</h3>
      <div style="background:#f8f6f1;border-radius:10px;padding:20px;margin:0 0 24px;">
        <p style="margin:0 0 10px;color:#1a1a2e;">
          <strong>1.</strong> Go to your <a href="https://dorjea.com/dashboard" style="color:#2563eb;">Dashboard</a>
        </p>
        <p style="margin:0 0 10px;color:#1a1a2e;">
          <strong>2.</strong> Click <strong>Create Agent</strong> and describe a business role
        </p>
        <p style="margin:0;color:#1a1a2e;">
          <strong>3.</strong> Assign your first task and watch it work
        </p>
      </div>
      <a href="https://dorjea.com/dashboard"
         style="display:inline-block;padding:14px 32px;background:#2563eb;color:#fff;
                border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
        Go to Dashboard →
      </a>
      <p style="color:#6b6b80;font-size:13px;margin:24px 0 0;">
        Questions? Reply to this email or contact
        <a href="mailto:support@dorjea.com" style="color:#2563eb;">support@dorjea.com</a>
      </p>"""
    return send_email(to_email, "Welcome to Dorjea — Your AI workforce is ready", _base_template(content, "Welcome to Dorjea"))

def send_budget_warning_email(to_email: str, name: str, percent_used: float, tokens_remaining: int) -> bool:
    content = f"""
      <h2 style="color:#f59e0b;font-size:24px;margin:0 0 16px;">⚠️ Token Budget Alert</h2>
      <p style="color:#6b6b80;line-height:1.7;margin:0 0 20px;">
        Hi {name}, you have used <strong style="color:#f59e0b;">{percent_used:.0f}%</strong>
        of your daily token budget. Only <strong>{tokens_remaining:,} tokens</strong> remaining today.
      </p>
      <div style="background:#fffbeb;border-radius:10px;padding:20px;margin:0 0 24px;border:1px solid #fcd34d;">
        <p style="margin:0;color:#92400e;">
          Your token budget resets at <strong>midnight UTC</strong>.
          To increase your daily limit, upgrade your plan.
        </p>
      </div>
      <a href="https://dorjea.com/payment"
         style="display:inline-block;padding:14px 32px;background:#2563eb;color:#fff;
                border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
        Upgrade Plan →
      </a>"""
    return send_email(to_email, "Dorjea: 80% of your daily token budget used", _base_template(content, "Token Budget Warning"))

def send_payment_confirmation_email(to_email: str, name: str, plan: str, amount: float) -> bool:
    content = f"""
      <h2 style="color:#16a34a;font-size:24px;margin:0 0 16px;">✓ Payment Confirmed</h2>
      <p style="color:#6b6b80;line-height:1.7;margin:0 0 20px;">
        Hi {name}, your payment has been processed successfully.
      </p>
      <div style="background:#f0fdf4;border-radius:10px;padding:20px;margin:0 0 24px;border:1px solid #86efac;">
        <p style="margin:0 0 8px;color:#15803d;"><strong>Plan:</strong> {plan.title()}</p>
        <p style="margin:0 0 8px;color:#15803d;"><strong>Amount:</strong> /month</p>
        <p style="margin:0;color:#15803d;"><strong>Status:</strong> Active</p>
      </div>
      <a href="https://dorjea.com/billing"
         style="display:inline-block;padding:14px 32px;background:#2563eb;color:#fff;
                border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
        View Billing Details →
      </a>"""
    return send_email(to_email, f"Dorjea: Payment confirmed — {plan.title()} Plan", _base_template(content, "Payment Confirmed"))

def send_ticket_confirmation_email(to_email: str, name: str, ticket_id: str, subject: str, response_time: str) -> bool:
    content = f"""
      <h2 style="color:#1a1a2e;font-size:24px;margin:0 0 16px;">🎫 Support Ticket Received</h2>
      <p style="color:#6b6b80;line-height:1.7;margin:0 0 20px;">
        Hi {name}, we have received your support request.
      </p>
      <div style="background:#f8f6f1;border-radius:10px;padding:20px;margin:0 0 24px;">
        <p style="margin:0 0 8px;color:#1a1a2e;"><strong>Ticket ID:</strong> {ticket_id}</p>
        <p style="margin:0 0 8px;color:#1a1a2e;"><strong>Subject:</strong> {subject}</p>
        <p style="margin:0;color:#1a1a2e;"><strong>Expected Response:</strong> {response_time}</p>
      </div>
      <a href="https://dorjea.com/support"
         style="display:inline-block;padding:14px 32px;background:#2563eb;color:#fff;
                border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
        View Ticket Status →
      </a>
      <p style="color:#6b6b80;font-size:13px;margin:24px 0 0;">
        For urgent issues, email <a href="mailto:support@dorjea.com" style="color:#2563eb;">support@dorjea.com</a> directly.
      </p>"""
    return send_email(to_email, f"Dorjea Support: Ticket {ticket_id} received", _base_template(content, "Support Ticket Confirmed"))

def send_agent_created_email(to_email: str, name: str, agent_name: str, dna_score: float) -> bool:
    grade = "A" if dna_score >= 90 else "B" if dna_score >= 75 else "C"
    content = f"""
      <h2 style="color:#1a1a2e;font-size:24px;margin:0 0 16px;">🤖 Agent Created Successfully</h2>
      <p style="color:#6b6b80;line-height:1.7;margin:0 0 20px;">
        Hi {name}, your new AI agent is ready and deployed.
      </p>
      <div style="background:#f8f6f1;border-radius:10px;padding:20px;margin:0 0 24px;">
        <p style="margin:0 0 8px;color:#1a1a2e;"><strong>Agent:</strong> {agent_name}</p>
        <p style="margin:0 0 8px;color:#1a1a2e;"><strong>DNA Score:</strong> {dna_score:.1f}%</p>
        <p style="margin:0;color:#1a1a2e;"><strong>Grade:</strong>
          <span style="color:{"#16a34a" if grade=="A" else "#f59e0b" if grade=="B" else "#dc2626"};">
            Grade {grade}
          </span>
        </p>
      </div>
      <a href="https://dorjea.com/dashboard"
         style="display:inline-block;padding:14px 32px;background:#2563eb;color:#fff;
                border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
        Run Your First Task →
      </a>"""
    return send_email(to_email, f"Dorjea: Agent {agent_name} is ready", _base_template(content, "Agent Created"))

class TestEmailRequest(BaseModel):
    to_email: str
    type: str = "welcome"
    name: Optional[str] = "Test User"

@router.post("/test")
def test_notification(req: TestEmailRequest):
    if req.type == "welcome":
        result = send_welcome_email(req.to_email, req.name, "professional")
    elif req.type == "budget":
        result = send_budget_warning_email(req.to_email, req.name, 82.5, 9000)
    elif req.type == "ticket":
        result = send_ticket_confirmation_email(req.to_email, req.name, "TKT-TEST01", "Test issue", "24 hours")
    else:
        result = send_welcome_email(req.to_email, req.name, "free")
    return {"sent": result, "note": "Check SMTP_USER and SMTP_PASS env vars if email not received"}

@router.get("/history")
def get_notification_history():
    if not os.path.exists(NOTIFICATIONS_FILE):
        return {"notifications": [], "total": 0}
    with open(NOTIFICATIONS_FILE, encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]
    return {"notifications": records[-50:][::-1], "total": len(records)}