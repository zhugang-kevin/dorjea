import os
import json
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents.meta_agent.plan_enforcement import enforce_clone_limit

router = APIRouter(prefix="/clones", tags=["Department Clones"])
CLONES_FILE = "memory/department_clones.jsonl"

DEPARTMENTS = {
    "engineering": {"name":"Engineering","icon":"⚙️","color":"#2563eb","desc":"Technical development, coding, infrastructure"},
    "marketing": {"name":"Marketing","icon":"📣","color":"#f59e0b","desc":"Content, campaigns, SEO, social media, brand"},
    "sales": {"name":"Sales","icon":"💼","color":"#16a34a","desc":"Lead generation, outreach, pipeline management"},
    "operations": {"name":"Operations","icon":"🔄","color":"#7c3aed","desc":"Process automation, reporting, coordination"},
    "research": {"name":"Research","icon":"🔬","color":"#0284c7","desc":"Market intelligence, analysis, competitive research"},
    "strategy": {"name":"Strategy","icon":"🎯","color":"#dc2626","desc":"Planning, decisions, business development"},
}

def load_clones():
    if not os.path.exists(CLONES_FILE):
        return []
    with open(CLONES_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def save_clone(clone):
    with open(CLONES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(clone) + "\n")

def rewrite_clones(clones):
    with open(CLONES_FILE, "w", encoding="utf-8") as f:
        for c in clones:
            f.write(json.dumps(c) + "\n")

class CreateCloneRequest(BaseModel):
    user_email: str
    department: str
    clone_name: str
    description: Optional[str] = ""

class UpdateCloneRequest(BaseModel):
    clone_id: str
    user_email: str
    clone_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

@router.get("/departments")
def get_departments():
    return {"departments": [
        {"id": k, **v} for k, v in DEPARTMENTS.items()
    ]}

@router.post("/create")
def create_clone(req: CreateCloneRequest):
    if req.department not in DEPARTMENTS:
        raise HTTPException(400, detail="Invalid department")
    clones = load_clones()
    user_clones = [c for c in clones if c["user_email"] == req.user_email and not c.get("deleted")]
    enforce_clone_limit(req.user_email)
    if len(user_clones) >= 10:
        raise HTTPException(400, detail="Maximum 10 department clones per account")
    existing = [c for c in user_clones if c["department"] == req.department]
    if existing:
        raise HTTPException(400, detail="You already have a clone for this department")
    dept = DEPARTMENTS[req.department]
    clone = {
        "clone_id": "CLN-" + secrets.token_hex(6).upper(),
        "user_email": req.user_email,
        "department": req.department,
        "clone_name": req.clone_name or dept["name"] + " Team",
        "description": req.description or dept["desc"],
        "icon": dept["icon"],
        "color": dept["color"],
        "status": "active",
        "agents": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "agent_count": 0,
        "task_count": 0,
    }
    save_clone(clone)
    return {"clone": clone, "message": "Department clone created successfully"}

@router.get("/list/{user_email}")
def list_clones(user_email: str):
    clones = load_clones()
    user_clones = [c for c in clones
                   if c["user_email"] == user_email and not c.get("deleted")]
    available = [
        {"id": k, **v} for k, v in DEPARTMENTS.items()
        if k not in [c["department"] for c in user_clones]
    ]
    return {"clones": user_clones, "total": len(user_clones), "available_departments": available}

@router.post("/update")
def update_clone(req: UpdateCloneRequest):
    clones = load_clones()
    for c in clones:
        if c["clone_id"] == req.clone_id and c["user_email"] == req.user_email:
            if req.clone_name: c["clone_name"] = req.clone_name
            if req.description: c["description"] = req.description
            if req.status: c["status"] = req.status
            c["updated_at"] = datetime.utcnow().isoformat()
            rewrite_clones(clones)
            return {"message": "Clone updated", "clone": c}
    raise HTTPException(404, detail="Clone not found")

@router.delete("/delete/{clone_id}/{user_email}")
def delete_clone(clone_id: str, user_email: str):
    clones = load_clones()
    for c in clones:
        if c["clone_id"] == clone_id and c["user_email"] == user_email:
            c["deleted"] = True
            c["deleted_at"] = datetime.utcnow().isoformat()
            rewrite_clones(clones)
            return {"message": "Clone deleted"}
    raise HTTPException(404, detail="Clone not found")