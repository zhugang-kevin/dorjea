import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/billing", tags=["Billing"])
USERS_FILE = "memory/users.jsonl"
BILLING_FILE = "memory/billing_history.jsonl"

def load_user(email: str):
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                u = json.loads(line)
                if u.get("email") == email:
                    return u
    return None

def load_billing(email: str):
    if not os.path.exists(BILLING_FILE):
        return []
    with open(BILLING_FILE, encoding="utf-8") as f:
        all_records = [json.loads(l) for l in f if l.strip()]
    return [r for r in all_records if r.get("user_email") == email]

def save_billing(record):
    with open(BILLING_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

PLAN_PRICES = {
    "free": 0,
    "professional": 29,
    "business": 99,
    "enterprise": 0,
}

PLAN_DETAILS = {
    "free":         {"name":"Starter","daily_tokens":5000,"max_agents":3,"max_clones":0},
    "professional": {"name":"Professional","daily_tokens":50000,"max_agents":20,"max_clones":1},
    "business":     {"name":"Business","daily_tokens":250000,"max_agents":100,"max_clones":3},
    "enterprise":   {"name":"Enterprise","daily_tokens":1000000,"max_agents":500,"max_clones":10},
}

class RefundRequest(BaseModel):
    user_email: str
    reason: str
    additional_info: Optional[str] = ""

class CancelRequest(BaseModel):
    user_email: str
    reason: str

@router.get("/summary/{user_email}")
def get_billing_summary(user_email: str):
    user = load_user(user_email)
    if not user:
        raise HTTPException(404, detail="User not found")
    plan = user.get("plan", "free")
    price = PLAN_PRICES.get(plan, 0)
    plan_info = PLAN_DETAILS.get(plan, PLAN_DETAILS["free"])
    created_at = user.get("created_at", datetime.utcnow().isoformat())
    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z",""))
    except:
        created_dt = datetime.utcnow()
    now = datetime.utcnow()
    if plan != "free" and price > 0:
        days_since_created = (now - created_dt).days
        billing_day = created_dt.day
        if now.day >= billing_day:
            next_billing = now.replace(day=billing_day) + timedelta(days=32)
            next_billing = next_billing.replace(day=billing_day)
        else:
            next_billing = now.replace(day=billing_day)
        days_in_period = 30
        days_used = (now - now.replace(day=billing_day)).days if now.day >= billing_day else 30 - (now.replace(day=billing_day) - now).days
        days_remaining = days_in_period - days_used
        amount_used = round(price * days_used / days_in_period, 2)
        refund_amount = round(price - amount_used, 2)
    else:
        next_billing = None
        days_remaining = 0
        amount_used = 0
        refund_amount = 0
        if plan == "free":
            trial_days = user.get("trial_days", 3)
            trial_end = created_dt + timedelta(days=trial_days)
            days_remaining = max(0, (trial_end - now).days)
    history = load_billing(user_email)
    return {
        "plan": plan,
        "plan_name": plan_info["name"],
        "price_per_month": price,
        "next_billing_date": next_billing.isoformat() if next_billing else None,
        "days_remaining": days_remaining,
        "amount_used_this_period": amount_used,
        "refund_eligible": refund_amount,
        "plan_details": plan_info,
        "member_since": created_at,
        "billing_history": history[-10:][::-1],
        "payment_method": user.get("payment_method", None),
        "stripe_customer_id": user.get("stripe_customer_id", None),
    }

@router.post("/refund-request")
def request_refund(req: RefundRequest):
    user = load_user(req.user_email)
    if not user:
        raise HTTPException(404, detail="User not found")
    plan = user.get("plan", "free")
    price = PLAN_PRICES.get(plan, 0)
    if price == 0:
        raise HTTPException(400, detail="No active paid subscription to refund")
    now = datetime.utcnow()
    created_at = user.get("created_at", now.isoformat())
    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z",""))
    except:
        created_dt = now
    billing_day = created_dt.day
    if now.day >= billing_day:
        period_start = now.replace(day=billing_day)
    else:
        prev_month = now.replace(day=1) - timedelta(days=1)
        period_start = prev_month.replace(day=billing_day)
    days_used = (now - period_start).days
    days_in_period = 30
    amount_used = round(price * days_used / days_in_period, 2)
    refund_amount = round(price - amount_used, 2)
    record = {
        "type": "refund_request",
        "user_email": req.user_email,
        "plan": plan,
        "price_paid": price,
        "days_used": days_used,
        "amount_used": amount_used,
        "refund_amount": refund_amount,
        "reason": req.reason,
        "additional_info": req.additional_info,
        "status": "pending",
        "requested_at": now.isoformat(),
    }
    save_billing(record)
    return {
        "message": "Refund request submitted successfully",
        "refund_amount": refund_amount,
        "days_used": days_used,
        "calculation": f"Paid  - Used {days_used} days () = Refund ",
        "processing_time": "3-5 business days",
        "contact": "billing@dorjea.com",
    }

@router.post("/cancel")
def cancel_subscription(req: CancelRequest):
    user = load_user(req.user_email)
    if not user:
        raise HTTPException(404, detail="User not found")
    plan = user.get("plan", "free")
    if plan == "free":
        raise HTTPException(400, detail="No paid subscription to cancel")
    record = {
        "type": "cancellation_request",
        "user_email": req.user_email,
        "plan": plan,
        "reason": req.reason,
        "status": "pending",
        "requested_at": datetime.utcnow().isoformat(),
    }
    save_billing(record)
    return {
        "message": "Cancellation request received",
        "effective_date": "End of current billing period",
        "note": "Your plan remains active until the end of the current billing period. You will not be charged again.",
        "contact": "billing@dorjea.com",
    }

@router.get("/history/{user_email}")
def get_billing_history(user_email: str):
    history = load_billing(user_email)
    return {"history": history[::-1], "total": len(history)}