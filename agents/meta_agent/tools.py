import os
import json
import httpx
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/tools", tags=["Tool Integrations"])
TOOL_LOGS_FILE = "memory/tool_logs.jsonl"

def log_tool_use(tool: str, user_email: str, input_summary: str, output_summary: str, success: bool):
    record = {
        "tool": tool,
        "user_email": user_email,
        "input": input_summary[:200],
        "output": output_summary[:200],
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(TOOL_LOGS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

# ─── WEB SEARCH ─────────────────────────────────────────────────────────────

class WebSearchRequest(BaseModel):
    query: str
    user_email: str
    max_results: int = 5

class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str

@router.post("/web-search")
async def web_search(req: WebSearchRequest):
    if not req.query.strip():
        raise HTTPException(400, detail="Search query cannot be empty")
    
    api_key = os.getenv("SERPER_API_KEY") or os.getenv("GOOGLE_SEARCH_API_KEY")
    
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json={"q": req.query, "num": req.max_results}
                )
                data = res.json()
                results = []
                for item in data.get("organic", [])[:req.max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    })
                log_tool_use("web_search", req.user_email, req.query, f"{len(results)} results found", True)
                return {"results": results, "query": req.query, "total": len(results), "source": "serper"}
        except Exception as e:
            pass
    
    # Fallback: DuckDuckGo instant answer API
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": req.query, "format": "json", "no_redirect": 1, "no_html": 1}
            )
            data = res.json()
            results = []
            
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", req.query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("AbstractText", "")[:300],
                })
            
            for topic in data.get("RelatedTopics", [])[:req.max_results-1]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")[:300],
                    })
            
            if not results:
                results.append({
                    "title": f"Search results for: {req.query}",
                    "url": f"https://duckduckgo.com/?q={req.query.replace(' ', '+')}",
                    "snippet": f"Click to see full search results for {req.query} on DuckDuckGo.",
                })
            
            log_tool_use("web_search", req.user_email, req.query, f"{len(results)} results", True)
            return {"results": results[:req.max_results], "query": req.query, "total": len(results), "source": "duckduckgo"}
    
    except Exception as e:
        log_tool_use("web_search", req.user_email, req.query, str(e), False)
        raise HTTPException(500, detail=f"Search failed: {str(e)}")

# ─── EMAIL SENDING ───────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    user_email: str
    to_email: str
    subject: str
    body: str
    is_html: bool = False

@router.post("/send-email")
def send_email_tool(req: SendEmailRequest):
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    
    if not smtp_user or not smtp_pass:
        raise HTTPException(503, detail="Email service not configured. Add SMTP_USER and SMTP_PASS to environment variables.")
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = req.subject
        msg["From"] = smtp_user
        msg["To"] = req.to_email
        
        if req.is_html:
            msg.attach(MIMEText(req.body, "html"))
        else:
            msg.attach(MIMEText(req.body, "plain"))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, req.to_email, msg.as_string())
        
        log_tool_use("send_email", req.user_email, f"To:{req.to_email} Subject:{req.subject}", "Email sent successfully", True)
        return {"success": True, "message": f"Email sent to {req.to_email}", "subject": req.subject}
    
    except Exception as e:
        log_tool_use("send_email", req.user_email, f"To:{req.to_email}", str(e), False)
        raise HTTPException(500, detail=f"Email failed: {str(e)}")

# ─── WEBHOOK ─────────────────────────────────────────────────────────────────

class WebhookRequest(BaseModel):
    user_email: str
    url: str
    payload: dict
    method: str = "POST"
    headers: Optional[dict] = {}

@router.post("/webhook")
async def send_webhook(req: WebhookRequest):
    if not req.url.startswith("http"):
        raise HTTPException(400, detail="Webhook URL must start with http or https")
    
    allowed_methods = ["POST", "GET", "PUT", "PATCH"]
    if req.method.upper() not in allowed_methods:
        raise HTTPException(400, detail=f"Method must be one of: {allowed_methods}")
    
    try:
        headers = {"Content-Type": "application/json", **(req.headers or {})}
        async with httpx.AsyncClient(timeout=15) as client:
            if req.method.upper() == "GET":
                res = await client.get(req.url, headers=headers, params=req.payload)
            else:
                method = getattr(client, req.method.lower())
                res = await method(req.url, headers=headers, json=req.payload)
        
        log_tool_use("webhook", req.user_email, f"{req.method} {req.url}", f"Status {res.status_code}", res.status_code < 400)
        return {
            "success": res.status_code < 400,
            "status_code": res.status_code,
            "url": req.url,
            "response": res.text[:500] if res.text else "",
        }
    except Exception as e:
        log_tool_use("webhook", req.user_email, req.url, str(e), False)
        raise HTTPException(500, detail=f"Webhook failed: {str(e)}")

# ─── SLACK NOTIFICATION ───────────────────────────────────────────────────────

class SlackRequest(BaseModel):
    user_email: str
    webhook_url: str
    message: str
    channel: Optional[str] = ""
    username: Optional[str] = "Dorjea Agent"
    icon_emoji: Optional[str] = ":robot_face:"

@router.post("/slack")
async def send_slack(req: SlackRequest):
    if not req.webhook_url.startswith("https://hooks.slack.com"):
        raise HTTPException(400, detail="Invalid Slack webhook URL. Must start with https://hooks.slack.com")
    
    payload = {
        "text": req.message,
        "username": req.username or "Dorjea Agent",
        "icon_emoji": req.icon_emoji or ":robot_face:",
    }
    if req.channel:
        payload["channel"] = req.channel
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(req.webhook_url, json=payload)
        
        success = res.status_code == 200 and res.text == "ok"
        log_tool_use("slack", req.user_email, req.message[:100], f"Status {res.status_code}", success)
        
        if not success:
            raise HTTPException(400, detail=f"Slack returned: {res.text}")
        
        return {"success": True, "message": "Slack notification sent successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        log_tool_use("slack", req.user_email, req.message[:100], str(e), False)
        raise HTTPException(500, detail=f"Slack notification failed: {str(e)}")

# ─── GOOGLE SHEETS ────────────────────────────────────────────────────────────

class SheetsReadRequest(BaseModel):
    user_email: str
    spreadsheet_id: str
    range: str
    api_key: str

class SheetsWriteRequest(BaseModel):
    user_email: str
    spreadsheet_id: str
    range: str
    values: List[List[str]]
    api_key: str

@router.post("/sheets/read")
async def read_sheets(req: SheetsReadRequest):
    try:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{req.spreadsheet_id}/values/{req.range}"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, params={"key": req.api_key})
        
        if res.status_code != 200:
            raise HTTPException(400, detail=f"Google Sheets error: {res.json().get('error', {}).get('message', 'Unknown error')}")
        
        data = res.json()
        values = data.get("values", [])
        log_tool_use("sheets_read", req.user_email, f"Sheet:{req.spreadsheet_id} Range:{req.range}", f"{len(values)} rows", True)
        return {"values": values, "rows": len(values), "range": req.range}
    
    except HTTPException:
        raise
    except Exception as e:
        log_tool_use("sheets_read", req.user_email, req.spreadsheet_id, str(e), False)
        raise HTTPException(500, detail=f"Sheets read failed: {str(e)}")

# ─── TOOL LOGS ────────────────────────────────────────────────────────────────

@router.get("/logs/{user_email}")
def get_tool_logs(user_email: str):
    if not os.path.exists(TOOL_LOGS_FILE):
        return {"logs": [], "total": 0}
    with open(TOOL_LOGS_FILE, encoding="utf-8") as f:
        all_logs = [json.loads(l) for l in f if l.strip()]
    user_logs = [l for l in all_logs if l.get("user_email") == user_email]
    return {"logs": user_logs[-50:][::-1], "total": len(user_logs)}

@router.get("/available")
def get_available_tools():
    return {
        "tools": [
            {"id": "web_search", "name": "Web Search", "icon": "🔍", "description": "Search the internet for real-time information", "endpoint": "/tools/web-search", "requires_config": False},
            {"id": "send_email", "name": "Email Sender", "icon": "📧", "description": "Send emails via your configured SMTP", "endpoint": "/tools/send-email", "requires_config": True, "config": ["SMTP_USER", "SMTP_PASS"]},
            {"id": "webhook", "name": "Webhook", "icon": "🔗", "description": "Send data to any external URL or Zapier", "endpoint": "/tools/webhook", "requires_config": False},
            {"id": "slack", "name": "Slack", "icon": "💬", "description": "Send notifications to Slack channels", "endpoint": "/tools/slack", "requires_config": True, "config": ["Slack Webhook URL"]},
            {"id": "sheets", "name": "Google Sheets", "icon": "📊", "description": "Read and write Google Sheets data", "endpoint": "/tools/sheets/read", "requires_config": True, "config": ["Google API Key", "Spreadsheet ID"]},
        ]
    }