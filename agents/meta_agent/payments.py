import os, stripe
from datetime import datetime
from agents.meta_agent.auth import load_users, save_user

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PLAN_AMOUNTS_USD = {"professional": 4900, "business": 19900, "enterprise": 99900}
PLAN_NAMES = {
    "professional": "Dorjea Professional — 100,000 tokens/day",
    "business": "Dorjea Business — 500,000 tokens/day",
    "enterprise": "Dorjea Enterprise — Unlimited tokens/day",
}

def create_checkout_session(user_email, plan, success_url, cancel_url):
    if not stripe.api_key:
        return None, "Stripe not configured. Add STRIPE_SECRET_KEY to .env"
    if plan not in PLAN_AMOUNTS_USD:
        return None, "Invalid plan"
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "usd",
                "product_data": {"name": PLAN_NAMES[plan]},
                "unit_amount": PLAN_AMOUNTS_USD[plan],
                "recurring": {"interval": "month"}}, "quantity": 1}],
            mode="subscription",
            customer_email=user_email,
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}&plan=" + plan,
            cancel_url=cancel_url,
            metadata={"user_email": user_email, "plan": plan},
        )
        return session, None
    except Exception as e:
        return None, str(e)

def upgrade_user_plan(user_email, plan):
    users = load_users()
    user = users.get(user_email)
    if not user:
        return False, "User not found"
    user["plan"] = plan
    user["plan_upgraded_at"] = datetime.utcnow().isoformat()
    save_user(user)
    return True, "Plan upgraded to " + plan

def handle_webhook(payload, sig_header):
    if not STRIPE_WEBHOOK_SECRET:
        return False, "Webhook secret not configured"
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return False, str(e)
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email") or session.get("metadata", {}).get("user_email")
        plan = session.get("metadata", {}).get("plan", "professional")
        if email:
            upgrade_user_plan(email, plan)
    return True, "OK"

def get_payment_config():
    return {
        "stripe_configured": bool(stripe.api_key),
        "plans": {
            "professional": {"price_usd": 49, "tokens_day": 100000},
            "business": {"price_usd": 199, "tokens_day": 500000},
            "enterprise": {"price_usd": 999, "tokens_day": "unlimited"},
        }
    }
