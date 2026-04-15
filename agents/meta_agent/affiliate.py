import json, secrets, hashlib
from datetime import datetime
from pathlib import Path
from agents.meta_agent.auth import load_users, save_user

AFFILIATES_DB = Path("memory/affiliates.jsonl")
REFERRALS_DB = Path("memory/referrals.jsonl")

COMMISSION_RATES = {
    "professional": 0.20,
    "business": 0.20,
    "enterprise": 0.15,
}

PLAN_AMOUNTS = {
    "professional": 49,
    "business": 199,
    "enterprise": 999,
}


def load_affiliates():
    if not AFFILIATES_DB.exists():
        return {}
    affiliates = {}
    try:
        with open(AFFILIATES_DB, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    a = json.loads(line)
                    affiliates[a["email"]] = a
    except Exception:
        pass
    return affiliates


def save_affiliate(affiliate: dict):
    AFFILIATES_DB.parent.mkdir(parents=True, exist_ok=True)
    affiliates = load_affiliates()
    affiliates[affiliate["email"]] = affiliate
    with open(AFFILIATES_DB, "w", encoding="utf-8") as f:
        for a in affiliates.values():
            f.write(json.dumps(a) + chr(10))


def load_referrals():
    if not REFERRALS_DB.exists():
        return []
    referrals = []
    try:
        with open(REFERRALS_DB, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    referrals.append(json.loads(line))
    except Exception:
        pass
    return referrals


def save_referral(referral: dict):
    REFERRALS_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(REFERRALS_DB, "a", encoding="utf-8") as f:
        f.write(json.dumps(referral) + chr(10))


def create_affiliate(email: str, name: str):
    affiliates = load_affiliates()
    if email in affiliates:
        return affiliates[email], None
    code = secrets.token_hex(6).upper()
    affiliate = {
        "email": email,
        "name": name,
        "code": code,
        "referral_link": "https://dorjea.ai/login?ref=" + code,
        "total_referrals": 0,
        "paid_referrals": 0,
        "total_commission_usd": 0.0,
        "pending_commission_usd": 0.0,
        "paid_commission_usd": 0.0,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }
    save_affiliate(affiliate)
    return affiliate, None


def record_referral(affiliate_code: str, referred_email: str, plan: str):
    affiliates = load_affiliates()
    affiliate = None
    for a in affiliates.values():
        if a["code"] == affiliate_code:
            affiliate = a
            break
    if not affiliate:
        return False, "Invalid affiliate code"
    amount = PLAN_AMOUNTS.get(plan, 0)
    rate = COMMISSION_RATES.get(plan, 0.20)
    commission = round(amount * rate, 2)
    referral = {
        "id": secrets.token_hex(8),
        "affiliate_code": affiliate_code,
        "affiliate_email": affiliate["email"],
        "referred_email": referred_email,
        "plan": plan,
        "amount_usd": amount,
        "commission_usd": commission,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    save_referral(referral)
    affiliate["total_referrals"] += 1
    affiliate["total_commission_usd"] = round(affiliate["total_commission_usd"] + commission, 2)
    affiliate["pending_commission_usd"] = round(affiliate["pending_commission_usd"] + commission, 2)
    save_affiliate(affiliate)
    return True, referral


def get_affiliate_stats(email: str):
    affiliates = load_affiliates()
    affiliate = affiliates.get(email)
    if not affiliate:
        return None
    referrals = [r for r in load_referrals() if r["affiliate_email"] == email]
    return {
        "affiliate": affiliate,
        "referrals": referrals,
        "summary": {
            "total_referrals": len(referrals),
            "paid_referrals": len([r for r in referrals if r["status"] == "paid"]),
            "pending_referrals": len([r for r in referrals if r["status"] == "pending"]),
            "total_commission": affiliate["total_commission_usd"],
            "pending_commission": affiliate["pending_commission_usd"],
            "paid_commission": affiliate["paid_commission_usd"],
        }
    }
