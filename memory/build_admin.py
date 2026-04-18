code = '''
import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from collections import defaultdict

router = APIRouter(prefix="/admin", tags=["Admin"])

USERS_FILE = "memory/users.jsonl"
AGENTS_FILE = "memory/agents.jsonl"
BILLING_FILE = "memory/billing_history.jsonl"
TICKETS_FILE = "memory/support_tickets.jsonl"
AUDIT_FILE = "memory/audit_log.jsonl"
TASKS_FILE = "memory/tasks.jsonl"
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "dorjea-admin-2026")

def verify_admin(authorization: str = Header(...)):
    if authorization != "Bearer " + ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin access denied")

def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def rewrite_jsonl(path, data):
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\\n")

PLAN_PRICES = {"free":0,"professional":29,"business":99,"enterprise":0}

@router.get("/overview")
def admin_overview(authorization: str = Header(...)):
    verify_admin(authorization)
    users = load_jsonl(USERS_FILE)
    agents = load_jsonl(AGENTS_FILE)
    tickets = load_jsonl(TICKETS_FILE)
    billing = load_jsonl(BILLING_FILE)
    tasks = load_jsonl(TASKS_FILE)

    now = datetime.utcnow()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    def parse_dt(s):
        try: return datetime.fromisoformat(str(s).replace("Z",""))
        except: return datetime.min

    # User stats
    total_users = len(users)
    new_users_7d = len([u for u in users if parse_dt(u.get("created_at","")) > last_7d])
    new_users_30d = len([u for u in users if parse_dt(u.get("created_at","")) > last_30d])

    # Plan breakdown
    plan_counts = defaultdict(int)
    for u in users:
        plan_counts[u.get("plan","free")] += 1

    # Revenue calculation
    mrr = sum(PLAN_PRICES.get(u.get("plan","free"),0) for u in users)

    # Active users (logged in last 7 days)
    active_users = len([u for u in users if parse_dt(u.get("last_login","")) > last_7d])

    # Ticket stats
    open_tickets = len([t for t in tickets if t.get("status") in ["open","in_progress"]])
    urgent_tickets = len([t for t in tickets if t.get("priority") == "urgent" and t.get("status") != "resolved"])

    # Agent stats
    total_agents = len([a for a in agents if not a.get("deleted")])
    active_agents = len([a for a in agents if a.get("status") == "active"])

    # Users by day (last 7 days)
    users_by_day = defaultdict(int)
    for u in users:
        dt = parse_dt(u.get("created_at",""))
        if dt > last_7d:
            users_by_day[dt.strftime("%Y-%m-%d")] += 1

    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6,-1,-1)]
    growth_chart = [{"date":d,"users":users_by_day.get(d,0)} for d in days]

    return {
        "summary": {
            "total_users": total_users,
            "new_users_7d": new_users_7d,
            "new_users_30d": new_users_30d,
            "active_users_7d": active_users,
            "mrr": mrr,
            "arr": mrr * 12,
            "total_agents": total_agents,
            "active_agents": active_agents,
            "open_tickets": open_tickets,
            "urgent_tickets": urgent_tickets,
        },
        "plan_breakdown": dict(plan_counts),
        "growth_chart": growth_chart,
        "recent_users": sorted(users, key=lambda x: x.get("created_at",""), reverse=True)[:10],
    }

@router.get("/users")
def list_all_users(authorization: str = Header(...), plan: str = None, search: str = None):
    verify_admin(authorization)
    users = load_jsonl(USERS_FILE)
    if plan:
        users = [u for u in users if u.get("plan") == plan]
    if search:
        search = search.lower()
        users = [u for u in users if search in u.get("email","").lower() or search in u.get("name","").lower()]
    # Remove password hashes
    safe_users = [{k:v for k,v in u.items() if k not in ["password_hash","salt"]} for u in users]
    safe_users.sort(key=lambda x: x.get("created_at",""), reverse=True)
    return {"users": safe_users, "total": len(safe_users)}

@router.get("/user/{email}")
def get_user_detail(email: str, authorization: str = Header(...)):
    verify_admin(authorization)
    users = load_jsonl(USERS_FILE)
    user = next((u for u in users if u.get("email") == email), None)
    if not user:
        raise HTTPException(404, detail="User not found")
    agents = load_jsonl(AGENTS_FILE)
    user_agents = [a for a in agents if a.get("user_email") == email]
    tickets = load_jsonl(TICKETS_FILE)
    user_tickets = [t for t in tickets if t.get("user_email") == email]
    billing = load_jsonl(BILLING_FILE)
    user_billing = [b for b in billing if b.get("user_email") == email]
    safe_user = {k:v for k,v in user.items() if k not in ["password_hash","salt"]}
    return {
        "user": safe_user,
        "agents": user_agents,
        "tickets": user_tickets,
        "billing": user_billing,
        "stats": {
            "total_agents": len(user_agents),
            "active_agents": len([a for a in user_agents if a.get("status")=="active"]),
            "total_tickets": len(user_tickets),
            "open_tickets": len([t for t in user_tickets if t.get("status")=="open"]),
        }
    }

class UpdateUserPlanRequest(BaseModel):
    email: str
    plan: str
    reason: Optional[str] = ""

class SuspendUserRequest(BaseModel):
    email: str
    suspended: bool
    reason: Optional[str] = ""

@router.post("/user/update-plan")
def admin_update_plan(req: UpdateUserPlanRequest, authorization: str = Header(...)):
    verify_admin(authorization)
    if req.plan not in ["free","professional","business","enterprise"]:
        raise HTTPException(400, detail="Invalid plan")
    users = load_jsonl(USERS_FILE)
    found = False
    for u in users:
        if u.get("email") == req.email:
            old_plan = u.get("plan","free")
            u["plan"] = req.plan
            u["plan_updated_at"] = datetime.utcnow().isoformat()
            u["plan_updated_by"] = "admin"
            found = True
            break
    if not found:
        raise HTTPException(404, detail="User not found")
    rewrite_jsonl(USERS_FILE, users)
    return {"message": f"Plan updated to {req.plan}", "email": req.email}

@router.post("/user/suspend")
def admin_suspend_user(req: SuspendUserRequest, authorization: str = Header(...)):
    verify_admin(authorization)
    users = load_jsonl(USERS_FILE)
    found = False
    for u in users:
        if u.get("email") == req.email:
            u["suspended"] = req.suspended
            u["suspension_reason"] = req.reason
            u["suspended_at"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(404, detail="User not found")
    rewrite_jsonl(USERS_FILE, users)
    action = "suspended" if req.suspended else "unsuspended"
    return {"message": f"User {action} successfully"}

@router.get("/tickets")
def admin_all_tickets(authorization: str = Header(...), status: str = None):
    verify_admin(authorization)
    tickets = load_jsonl(TICKETS_FILE)
    if status:
        tickets = [t for t in tickets if t.get("status") == status]
    tickets.sort(key=lambda x: x.get("updated_at",""), reverse=True)
    return {"tickets": tickets, "total": len(tickets)}

@router.get("/revenue")
def admin_revenue(authorization: str = Header(...)):
    verify_admin(authorization)
    users = load_jsonl(USERS_FILE)
    now = datetime.utcnow()
    plan_counts = defaultdict(int)
    for u in users:
        plan_counts[u.get("plan","free")] += 1
    mrr = sum(PLAN_PRICES.get(plan,0) * count for plan,count in plan_counts.items())
    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "plan_breakdown": {
            plan: {"count": count, "revenue": PLAN_PRICES.get(plan,0)*count}
            for plan, count in plan_counts.items()
        },
        "paying_users": sum(count for plan,count in plan_counts.items() if PLAN_PRICES.get(plan,0) > 0),
        "free_users": plan_counts.get("free",0),
        "conversion_rate": round(
            sum(count for plan,count in plan_counts.items() if PLAN_PRICES.get(plan,0) > 0)
            / max(len(users),1) * 100, 1
        ),
    }
'''

with open("agents/meta_agent/admin.py", "w", encoding="utf-8") as f:
    f.write(code.strip())
print("admin.py created")
