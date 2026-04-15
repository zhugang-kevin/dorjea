with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.payments import create_checkout_session, handle_webhook, get_payment_config, upgrade_user_plan"
new = """from agents.meta_agent.payments import create_checkout_session, handle_webhook, get_payment_config, upgrade_user_plan
from agents.meta_agent.affiliate import create_affiliate, get_affiliate_stats, record_referral"""

content = content.replace(old, new, 1)

content += '''

class AffiliateRequest(BaseModel):
    email: str
    name: str

class ReferralRequest(BaseModel):
    affiliate_code: str
    referred_email: str
    plan: str

@app.post("/affiliate/register")
def register_affiliate(body: AffiliateRequest) -> dict:
    affiliate, error = create_affiliate(body.email, body.name)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "SUCCESS", "affiliate": affiliate}

@app.get("/affiliate/{email}/stats")
def affiliate_stats(email: str, authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    stats = get_affiliate_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return stats

@app.post("/affiliate/referral")
def track_referral(body: ReferralRequest) -> dict:
    ok, result = record_referral(body.affiliate_code, body.referred_email, body.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "SUCCESS", "referral": result}
'''

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Affiliate endpoints added to API")
