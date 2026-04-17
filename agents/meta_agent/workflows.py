import os
import json
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/workflows", tags=["Workflows"])
WORKFLOWS_FILE = "memory/workflows.jsonl"
RUNS_FILE = "memory/workflow_runs.jsonl"

def load_workflows():
    if not os.path.exists(WORKFLOWS_FILE):
        return []
    with open(WORKFLOWS_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def save_workflow(wf):
    with open(WORKFLOWS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(wf) + "\n")

def rewrite_workflows(wfs):
    with open(WORKFLOWS_FILE, "w", encoding="utf-8") as f:
        for w in wfs:
            f.write(json.dumps(w) + "\n")

def load_runs():
    if not os.path.exists(RUNS_FILE):
        return []
    with open(RUNS_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def save_run(run):
    with open(RUNS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(run) + "\n")

def rewrite_runs(runs):
    with open(RUNS_FILE, "w", encoding="utf-8") as f:
        for r in runs:
            f.write(json.dumps(r) + "\n")

class WorkflowStep(BaseModel):
    step_id: str
    agent_name: str
    task_template: str
    use_previous_output: bool = True
    order: int

class CreateWorkflowRequest(BaseModel):
    user_email: str
    name: str
    description: str
    steps: List[WorkflowStep]
    trigger: str = "manual"

class RunWorkflowRequest(BaseModel):
    workflow_id: str
    user_email: str
    initial_input: str

class UpdateWorkflowRequest(BaseModel):
    workflow_id: str
    user_email: str
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[WorkflowStep]] = None
    status: Optional[str] = None

@router.post("/create")
def create_workflow(req: CreateWorkflowRequest):
    if len(req.steps) < 2:
        raise HTTPException(400, detail="Workflow must have at least 2 steps")
    if len(req.steps) > 10:
        raise HTTPException(400, detail="Maximum 10 steps per workflow")
    workflow = {
        "workflow_id": "WF-" + secrets.token_hex(6).upper(),
        "user_email": req.user_email,
        "name": req.name,
        "description": req.description,
        "steps": [s.dict() for s in req.steps],
        "trigger": req.trigger,
        "status": "active",
        "run_count": 0,
        "last_run": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    save_workflow(workflow)
    return {"workflow": workflow, "message": "Workflow created successfully"}

@router.get("/list/{user_email}")
def list_workflows(user_email: str):
    workflows = load_workflows()
    user_wfs = [w for w in workflows
                if w["user_email"] == user_email and not w.get("deleted")]
    user_wfs.sort(key=lambda x: x.get("updated_at",""), reverse=True)
    runs = load_runs()
    for wf in user_wfs:
        wf_runs = [r for r in runs if r["workflow_id"] == wf["workflow_id"]]
        wf["run_count"] = len(wf_runs)
        wf["last_run"] = wf_runs[-1]["started_at"] if wf_runs else None
    return {"workflows": user_wfs, "total": len(user_wfs)}

@router.get("/runs/{user_email}")
def list_runs(user_email: str):
    runs = load_runs()
    user_runs = [r for r in runs if r["user_email"] == user_email]
    user_runs.sort(key=lambda x: x.get("started_at",""), reverse=True)
    return {"runs": user_runs[:20], "total": len(user_runs)}

@router.post("/run")
async def run_workflow(req: RunWorkflowRequest, background_tasks: BackgroundTasks):
    workflows = load_workflows()
    wf = next((w for w in workflows
               if w["workflow_id"] == req.workflow_id
               and w["user_email"] == req.user_email), None)
    if not wf:
        raise HTTPException(404, detail="Workflow not found")
    run_id = "RUN-" + secrets.token_hex(6).upper()
    run = {
        "run_id": run_id,
        "workflow_id": req.workflow_id,
        "workflow_name": wf["name"],
        "user_email": req.user_email,
        "initial_input": req.initial_input,
        "status": "running",
        "current_step": 0,
        "total_steps": len(wf["steps"]),
        "step_results": [],
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "error": None,
    }
    save_run(run)
    background_tasks.add_task(_execute_workflow, run_id, wf, req.initial_input, req.user_email)
    return {"run_id": run_id, "status": "running",
            "message": "Workflow started. Check run status for progress."}

async def _execute_workflow(run_id: str, workflow: dict, initial_input: str, user_email: str):
    import asyncio
    runs = load_runs()
    run = next((r for r in runs if r["run_id"] == run_id), None)
    if not run:
        return
    try:
        previous_output = initial_input
        for i, step in enumerate(workflow["steps"]):
            await asyncio.sleep(1)
            task = step["task_template"]
            if step.get("use_previous_output") and previous_output:
                task = task + "\n\nContext from previous step:\n" + previous_output
            step_result = {
                "step_id": step["step_id"],
                "agent": step["agent_name"],
                "task": task[:200] + "..." if len(task) > 200 else task,
                "status": "completed",
                "output": "Step " + str(i+1) + " completed by " + step["agent_name"],
                "completed_at": datetime.utcnow().isoformat(),
            }
            previous_output = step_result["output"]
            runs = load_runs()
            run = next((r for r in runs if r["run_id"] == run_id), None)
            if run:
                run["step_results"].append(step_result)
                run["current_step"] = i + 1
                rewrite_runs(runs)
        runs = load_runs()
        run = next((r for r in runs if r["run_id"] == run_id), None)
        if run:
            run["status"] = "completed"
            run["completed_at"] = datetime.utcnow().isoformat()
            rewrite_runs(runs)
    except Exception as e:
        runs = load_runs()
        run = next((r for r in runs if r["run_id"] == run_id), None)
        if run:
            run["status"] = "failed"
            run["error"] = str(e)
            rewrite_runs(runs)

@router.get("/run/{run_id}")
def get_run_status(run_id: str):
    runs = load_runs()
    run = next((r for r in runs if r["run_id"] == run_id), None)
    if not run:
        raise HTTPException(404, detail="Run not found")
    return run

@router.post("/update")
def update_workflow(req: UpdateWorkflowRequest):
    workflows = load_workflows()
    for w in workflows:
        if w["workflow_id"] == req.workflow_id and w["user_email"] == req.user_email:
            if req.name: w["name"] = req.name
            if req.description: w["description"] = req.description
            if req.steps: w["steps"] = [s.dict() for s in req.steps]
            if req.status: w["status"] = req.status
            w["updated_at"] = datetime.utcnow().isoformat()
            rewrite_workflows(workflows)
            return {"message": "Workflow updated", "workflow": w}
    raise HTTPException(404, detail="Workflow not found")

@router.delete("/delete/{workflow_id}/{user_email}")
def delete_workflow(workflow_id: str, user_email: str):
    workflows = load_workflows()
    for w in workflows:
        if w["workflow_id"] == workflow_id and w["user_email"] == user_email:
            w["deleted"] = True
            rewrite_workflows(workflows)
            return {"message": "Workflow deleted"}
    raise HTTPException(404, detail="Workflow not found")