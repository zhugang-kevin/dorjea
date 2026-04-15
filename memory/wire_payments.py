with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.auth import ("
new = """from agents.meta_agent.payments import create_checkout_session, handle_webhook, get_payment_config, upgrade_user_plan
from agents.meta_agent.auth import ("""

content = content.replace(old, new, 1)

content += '''

class CheckoutRequest(BaseModel):
    plan: str
    user_email: str

@app.post("/payments/checkout")
def create_checkout(body: CheckoutRequest, request: Request) -> dict:
    success_url = "http://localhost:3000/payment/success"
    cancel_url = "http://localhost:3000/login"
    session, error = create_checkout_session(body.user_email, body.plan, success_url, cancel_url)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "checkout_url": session.url, "session_id": session.id}

@app.post("/payments/webhook")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    ok, msg = handle_webhook(payload, sig_header)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "OK"}

@app.post("/payments/upgrade")
def manual_upgrade(body: CheckoutRequest) -> dict:
    ok, msg = upgrade_user_plan(body.user_email, body.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}

@app.get("/payments/config")
def payment_config() -> dict:
    return get_payment_config()
'''

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Payment endpoints added to API")
