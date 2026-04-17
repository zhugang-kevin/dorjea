import os
import json
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/support", tags=["Support"])
TICKETS_FILE = "memory/support_tickets.jsonl"

def load_tickets():
    if not os.path.exists(TICKETS_FILE):
        return []
    with open(TICKETS_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def save_ticket(ticket):
    with open(TICKETS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(ticket) + "\n")

def rewrite_tickets(tickets):
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        for t in tickets:
            f.write(json.dumps(t) + "\n")

class CreateTicketRequest(BaseModel):
    user_email: str
    subject: str
    description: str
    category: str = "general"
    priority: str = "normal"

class ReplyRequest(BaseModel):
    ticket_id: str
    user_email: str
    message: str
    is_staff: bool = False

class UpdateStatusRequest(BaseModel):
    ticket_id: str
    status: str

CATEGORIES = ["general", "billing", "technical", "agent", "account", "feature_request"]
PRIORITIES = ["low", "normal", "high", "urgent"]
STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"]

@router.post("/tickets/create")
def create_ticket(req: CreateTicketRequest):
    if req.category not in CATEGORIES:
        raise HTTPException(400, detail="Invalid category")
    if req.priority not in PRIORITIES:
        raise HTTPException(400, detail="Invalid priority")
    ticket_id = "TKT-" + secrets.token_hex(4).upper()
    ticket = {
        "ticket_id": ticket_id,
        "user_email": req.user_email,
        "subject": req.subject,
        "description": req.description,
        "category": req.category,
        "priority": req.priority,
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "messages": [
            {
                "sender": req.user_email,
                "message": req.description,
                "is_staff": False,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
        "auto_reply": _get_auto_reply(req.category, req.priority),
    }
    save_ticket(ticket)
    return {"ticket_id": ticket_id, "status": "open",
            "message": "Ticket created successfully",
            "auto_reply": ticket["auto_reply"],
            "expected_response": _get_response_time(req.priority)}

@router.get("/tickets/{user_email}")
def get_user_tickets(user_email: str):
    tickets = load_tickets()
    user_tickets = [t for t in tickets if t["user_email"] == user_email]
    user_tickets.sort(key=lambda x: x.get("updated_at",""), reverse=True)
    return {"tickets": user_tickets, "total": len(user_tickets)}

@router.get("/ticket/{ticket_id}")
def get_ticket(ticket_id: str):
    tickets = load_tickets()
    for t in tickets:
        if t["ticket_id"] == ticket_id:
            return t
    raise HTTPException(404, detail="Ticket not found")

@router.post("/tickets/reply")
def reply_to_ticket(req: ReplyRequest):
    tickets = load_tickets()
    for t in tickets:
        if t["ticket_id"] == req.ticket_id:
            msg = {
                "sender": "Dorjea Support" if req.is_staff else req.user_email,
                "message": req.message,
                "is_staff": req.is_staff,
                "timestamp": datetime.utcnow().isoformat(),
            }
            t["messages"].append(msg)
            t["updated_at"] = datetime.utcnow().isoformat()
            if req.is_staff and t["status"] == "open":
                t["status"] = "in_progress"
            rewrite_tickets(tickets)
            return {"message": "Reply added", "ticket_id": req.ticket_id}
    raise HTTPException(404, detail="Ticket not found")

@router.post("/tickets/status")
def update_ticket_status(req: UpdateStatusRequest):
    if req.status not in STATUSES:
        raise HTTPException(400, detail="Invalid status")
    tickets = load_tickets()
    for t in tickets:
        if t["ticket_id"] == req.ticket_id:
            t["status"] = req.status
            t["updated_at"] = datetime.utcnow().isoformat()
            rewrite_tickets(tickets)
            return {"message": "Status updated", "status": req.status}
    raise HTTPException(404, detail="Ticket not found")

@router.get("/categories")
def get_categories():
    return {
        "categories": [
            {"id":"general","label":"General Question","icon":"❓"},
            {"id":"billing","label":"Billing and Payments","icon":"💳"},
            {"id":"technical","label":"Technical Issue","icon":"🔧"},
            {"id":"agent","label":"Agent Problem","icon":"🤖"},
            {"id":"account","label":"Account and Login","icon":"👤"},
            {"id":"feature_request","label":"Feature Request","icon":"💡"},
        ],
        "priorities": [
            {"id":"low","label":"Low - General inquiry","color":"#6b7280"},
            {"id":"normal","label":"Normal - Standard support","color":"#2563eb"},
            {"id":"high","label":"High - Affecting my work","color":"#f59e0b"},
            {"id":"urgent","label":"Urgent - System down","color":"#dc2626"},
        ]
    }

def _get_auto_reply(category, priority):
    if priority == "urgent":
        return "We have received your urgent ticket and our team has been notified immediately. We aim to respond within 1 hour."
    if priority == "high":
        return "Your ticket has been received with high priority. We will respond within 4 hours during business hours."
    if category == "billing":
        return "Thank you for contacting Dorjea support about billing. We will review your account and respond within 24 hours. For immediate help email support@dorjea.com"
    return "Thank you for contacting Dorjea support. We have received your ticket and will respond within 24 hours. You can track your ticket status on this page."

def _get_response_time(priority):
    times = {"urgent":"1 hour","high":"4 hours","normal":"24 hours","low":"48 hours"}
    return times.get(priority, "24 hours")