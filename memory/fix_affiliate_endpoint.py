with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """@app.get("/affiliate/{email}/stats")
def affiliate_stats(email: str, authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    stats = get_affiliate_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return stats"""

new = """@app.get("/affiliate/{email}/stats")
def affiliate_stats(email: str, authorization: str = Header(default="")) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    stats = get_affiliate_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return stats"""

content = content.replace(old, new)
with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed")
