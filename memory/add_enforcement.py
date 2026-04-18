with open("agents/meta_agent/api.py", encoding="utf-8") as f:
    content = f.read()

old = '''@app.post("/agents/create", response_model=CreateAgentResponse)
def create_agent(body: CreateAgentRequest) -> CreateAgentResponse:
    if not body.request or len(body.request.strip()) < 10:
        raise HTTPException(status_code=400, detail="Request must be at least 10 characters.")'''

new = '''@app.post("/agents/create", response_model=CreateAgentResponse)
def create_agent(body: CreateAgentRequest) -> CreateAgentResponse:
    if not body.request or len(body.request.strip()) < 10:
        raise HTTPException(status_code=400, detail="Request must be at least 10 characters.")
    # Plan enforcement - check agent limit
    try:
        user_email = getattr(body, "user_email", None)
        if user_email:
            enforce_agent_limit(user_email)
    except HTTPException:
        raise
    except Exception:
        pass'''

if old in content:
    content = content.replace(old, new)
    with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Agent limit enforcement added")
else:
    print("Pattern not found")
