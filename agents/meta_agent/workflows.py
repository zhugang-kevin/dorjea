from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from agents.meta_agent.plan_enforcement import require_feature, resolve_scoped_user_email
from agents.meta_agent.reliability import with_retry, score_output_confidence, validate_output
from agents.runtime.agent_runtime import runtime

WORKFLOW_TIMEOUT_SECONDS = int(os.getenv("WORKFLOW_STEP_TIMEOUT", "120"))

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
    dependencies=[Depends(require_feature("workflows"))],
)

WORKFLOWS_FILE = "memory/workflows.jsonl"
RUNS_FILE = "memory/workflow_runs.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _save_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_workflows() -> list[dict]:
    return _load_jsonl(WORKFLOWS_FILE)


def save_workflow(row: dict) -> None:
    rows = load_workflows()
    rows.append(row)
    _save_jsonl(WORKFLOWS_FILE, rows)


def rewrite_workflows(rows: list[dict]) -> None:
    _save_jsonl(WORKFLOWS_FILE, rows)


def load_runs() -> list[dict]:
    return _load_jsonl(RUNS_FILE)


def rewrite_runs(rows: list[dict]) -> None:
    _save_jsonl(RUNS_FILE, rows)


def save_run(row: dict) -> None:
    rows = load_runs()
    rows.append(row)
    rewrite_runs(rows)


def _update_run(run_id: str, mutator) -> dict | None:
    runs = load_runs()
    target = None
    for row in runs:
        if row.get("run_id") == run_id:
            mutator(row)
            target = row
            break
    if target is not None:
        rewrite_runs(runs)
    return target


class WorkflowStep(BaseModel):
    step_id: str
    agent_name: str
    task_template: str
    use_previous_output: bool = True
    order: int
    token_budget: int = 8000
    requires_approval: bool = False
    confidence_threshold: float = 0.55
    validation_rules: list[dict] = Field(default_factory=list)
    max_retries: int = 3


class CreateWorkflowRequest(BaseModel):
    user_email: Optional[str] = None
    name: str
    description: str = ""
    steps: list[WorkflowStep]
    trigger: str = "manual"


class RunWorkflowRequest(BaseModel):
    workflow_id: Optional[str] = None
    user_email: Optional[str] = None
    initial_input: str = ""
    name: Optional[str] = None
    steps: Optional[list[WorkflowStep]] = None


class UpdateWorkflowRequest(BaseModel):
    workflow_id: str
    user_email: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[list[WorkflowStep]] = None
    status: Optional[str] = None


class QuickWorkflowBody(BaseModel):
    name: str
    config: dict = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    run_id: str
    notes: str = ""


def _minimal_placeholder_steps() -> list[dict]:
    return [
        {
            "step_id": "s1",
            "agent_name": "_placeholder",
            "task_template": "请在可视化工作流编辑器中配置第一步",
            "use_previous_output": False,
            "order": 0,
            "token_budget": 2000,
            "requires_approval": False,
            "confidence_threshold": 0.55,
        },
        {
            "step_id": "s2",
            "agent_name": "_placeholder",
            "task_template": "请在可视化工作流编辑器中配置第二步",
            "use_previous_output": True,
            "order": 1,
            "token_budget": 2000,
            "requires_approval": False,
            "confidence_threshold": 0.55,
        },
    ]


def _normalize_steps(steps: list[WorkflowStep] | list[dict]) -> list[dict]:
    out: list[dict] = []
    for index, step in enumerate(steps):
        raw = step.model_dump() if isinstance(step, WorkflowStep) else dict(step)
        raw["order"] = index + 1
        raw.setdefault("token_budget", 8000)
        raw.setdefault("requires_approval", False)
        raw.setdefault("confidence_threshold", 0.55)
        out.append(raw)
    return out


def _workflow_payload_for_user(user_email: str) -> dict:
    workflows = [
        row for row in load_workflows()
        if row.get("user_email") == user_email and not row.get("deleted")
    ]
    workflows.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
    runs = load_runs()
    for workflow in workflows:
        workflow_runs = [run for run in runs if run.get("workflow_id") == workflow.get("workflow_id")]
        workflow["run_count"] = len(workflow_runs)
        workflow["last_run"] = workflow_runs[-1]["started_at"] if workflow_runs else None
    return {"workflows": workflows, "total": len(workflows)}


def _resolve_workflow_run(req: RunWorkflowRequest, user_email: str) -> tuple[dict, list[dict]]:
    if req.workflow_id:
        workflow = next(
            (
                row for row in load_workflows()
                if row.get("workflow_id") == req.workflow_id
                and row.get("user_email") == user_email
                and not row.get("deleted")
            ),
            None,
        )
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return workflow, _normalize_steps(workflow.get("steps", []))
    if not req.steps:
        raise HTTPException(status_code=400, detail="运行工作流时必须提供 workflow_id 或 steps")
    workflow = {
        "workflow_id": "WF-" + secrets.token_hex(6).upper(),
        "user_email": user_email,
        "name": (req.name or "Inline Workflow").strip() or "Inline Workflow",
        "description": "inline_run",
        "trigger": "manual",
        "status": "active",
        "created_at": _now(),
        "updated_at": _now(),
    }
    return workflow, _normalize_steps(req.steps)


def _build_step_prompt(step: dict, previous_output: str) -> str:
    prompt = step.get("task_template", "")
    if step.get("use_previous_output") and previous_output:
        prompt += "\n\nContext from previous step:\n" + previous_output
    return prompt.strip()


def _resume_workflow_run(run_id: str) -> None:
    import signal

    runs = load_runs()
    run = next((row for row in runs if row.get("run_id") == run_id), None)
    if not run:
        return
    if run.get("status") in {"completed", "failed", "rejected"}:
        return

    steps = list(run.get("steps_snapshot", []))
    current_idx = int(run.get("current_step", 0))
    previous_output = str(run.get("latest_output", "") or run.get("initial_input", ""))

    for idx in range(current_idx, len(steps)):
        step = steps[idx]
        step_id = str(step.get("step_id"))
        threshold = float(step.get("confidence_threshold", 0.55) or 0.55)
        validation_rules = step.get("validation_rules") or None

        if step.get("requires_approval") and step_id not in set(run.get("approved_steps", [])):
            run["status"] = "awaiting_approval"
            run["awaiting_step_id"] = step_id
            run["awaiting_step_order"] = idx + 1
            run["updated_at"] = _now()
            rewrite_runs(runs)
            return

        prompt = _build_step_prompt(step, previous_output)
        if not prompt:
            run["status"] = "failed"
            run["error"] = f"Step {idx + 1} 缺少任务描述"
            run["updated_at"] = _now()
            rewrite_runs(runs)
            return

        agent_name = str(step.get("agent_name"))

        def _run_step() -> dict:
            return runtime.run_task(agent_name, prompt, task_id=f"{run_id}:{step_id}")

        result = with_retry(
            _run_step,
            task_description=prompt,
            validation_rules=validation_rules,
            confidence_threshold=threshold,
        )

        reliability = result.get("reliability") or {}
        confidence = float(reliability.get("confidence", 0.0) or 0.0)

        # Re-score if runtime didn't attach reliability
        if confidence == 0.0 and result.get("output"):
            confidence = score_output_confidence(str(result.get("output", "")), prompt)
            result.setdefault("reliability", {})["confidence"] = confidence

        step_result = {
            "step_id": step_id,
            "agent": agent_name,
            "task": prompt[:200] + ("..." if len(prompt) > 200 else ""),
            "status": "completed" if result.get("status") == "SUCCESS" else "failed",
            "output": result.get("output", ""),
            "tokens_used": result.get("tokens_used", 0),
            "model_used": result.get("model_used"),
            "confidence": confidence,
            "confidence_threshold": threshold,
            "retries_used": reliability.get("retries_used", 0),
            "validation_passed": reliability.get("validation_passed", True),
            "completed_at": _now(),
        }
        run.setdefault("step_results", []).append(step_result)
        run["current_step"] = idx + 1
        run["updated_at"] = _now()

        if result.get("status") != "SUCCESS":
            run["status"] = "failed"
            run["error"] = result.get("error", "Workflow step failed")
            rewrite_runs(runs)
            return

        if confidence < threshold:
            run["status"] = "failed"
            run["error"] = f"步骤 {idx + 1} 置信度不足（{confidence:.2f} < {threshold:.2f}），已重试 {reliability.get('retries_used', 0)} 次"
            rewrite_runs(runs)
            return

        previous_output = str(result.get("output", "") or "")
        run["latest_output"] = previous_output
        run["status"] = "running"
        run["awaiting_step_id"] = None
        run["awaiting_step_order"] = None
        rewrite_runs(runs)

    run["status"] = "completed"
    run["completed_at"] = _now()
    run["updated_at"] = run["completed_at"]
    rewrite_runs(runs)


@router.get("")
def list_workflows_me(authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    return _workflow_payload_for_user(email)


@router.post("")
def create_workflow_root(body: QuickWorkflowBody, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="工作流名称不能为空")
    workflow = {
        "workflow_id": "WF-" + secrets.token_hex(6).upper(),
        "user_email": email,
        "name": name,
        "description": str(body.config.get("description", "") or ""),
        "steps": _minimal_placeholder_steps(),
        "trigger": "manual",
        "status": "active",
        "created_at": _now(),
        "updated_at": _now(),
    }
    save_workflow(workflow)
    return {"success": True, "workflow": workflow}


@router.delete("/{workflow_id}")
def delete_workflow_by_id(workflow_id: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    workflows = load_workflows()
    for workflow in workflows:
        if workflow.get("workflow_id") == workflow_id and workflow.get("user_email") == email:
            workflow["deleted"] = True
            workflow["deleted_at"] = _now()
            rewrite_workflows(workflows)
            return {"success": True, "message": "Workflow deleted"}
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/create")
def create_workflow(req: CreateWorkflowRequest, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(req.user_email, authorization)
    steps = _normalize_steps(req.steps)
    if len(steps) < 2:
        raise HTTPException(status_code=400, detail="Workflow must have at least 2 steps")
    if len(steps) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 steps per workflow")
    workflow = {
        "workflow_id": "WF-" + secrets.token_hex(6).upper(),
        "user_email": email,
        "name": req.name.strip(),
        "description": req.description,
        "steps": steps,
        "trigger": req.trigger,
        "status": "active",
        "created_at": _now(),
        "updated_at": _now(),
    }
    save_workflow(workflow)
    return {"workflow": workflow, "message": "Workflow created successfully"}


@router.get("/list/{user_email}")
def list_workflows(user_email: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(user_email, authorization)
    return _workflow_payload_for_user(email)


@router.get("/runs/{user_email}")
def list_runs(user_email: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(user_email, authorization)
    runs = [row for row in load_runs() if row.get("user_email") == email]
    runs.sort(key=lambda row: row.get("started_at", ""), reverse=True)
    return {"runs": runs[:50], "total": len(runs)}


@router.get("/approvals")
def list_pending_approvals(authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    runs = [
        row for row in load_runs()
        if row.get("user_email") == email and row.get("status") == "awaiting_approval"
    ]
    runs.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
    return {"runs": runs, "total": len(runs)}


@router.post("/run")
async def run_workflow(
    req: RunWorkflowRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
) -> dict:
    email = resolve_scoped_user_email(req.user_email, authorization)
    workflow, steps = _resolve_workflow_run(req, email)
    run_id = "RUN-" + secrets.token_hex(6).upper()
    run = {
        "run_id": run_id,
        "workflow_id": workflow["workflow_id"],
        "workflow_name": workflow["name"],
        "user_email": email,
        "initial_input": req.initial_input or "",
        "status": "running",
        "current_step": 0,
        "total_steps": len(steps),
        "steps_snapshot": steps,
        "step_results": [],
        "approved_steps": [],
        "awaiting_step_id": None,
        "awaiting_step_order": None,
        "latest_output": req.initial_input or "",
        "started_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "error": None,
    }
    save_run(run)
    background_tasks.add_task(_resume_workflow_run, run_id)
    return {"run_id": run_id, "status": "running", "message": "Workflow started"}


@router.post("/approve")
def approve_workflow_run(
    body: ApprovalRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
) -> dict:
    email = resolve_scoped_user_email(None, authorization)

    def mutator(row: dict) -> None:
        if row.get("user_email") != email:
            raise HTTPException(status_code=404, detail="Run not found")
        if row.get("status") != "awaiting_approval":
            raise HTTPException(status_code=400, detail="Run is not waiting for approval")
        step_id = row.get("awaiting_step_id")
        approved = set(row.get("approved_steps", []))
        if step_id:
            approved.add(step_id)
        row["approved_steps"] = list(approved)
        row["status"] = "running"
        row["approval_notes"] = body.notes
        row["updated_at"] = _now()

    run = _update_run(body.run_id, mutator)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    background_tasks.add_task(_resume_workflow_run, body.run_id)
    return {"success": True, "run_id": body.run_id, "status": "running"}


@router.post("/reject")
def reject_workflow_run(body: ApprovalRequest, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)

    def mutator(row: dict) -> None:
        if row.get("user_email") != email:
            raise HTTPException(status_code=404, detail="Run not found")
        row["status"] = "rejected"
        row["error"] = body.notes or "Workflow rejected by user"
        row["completed_at"] = _now()
        row["updated_at"] = row["completed_at"]

    run = _update_run(body.run_id, mutator)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"success": True, "run_id": body.run_id, "status": "rejected"}


@router.get("/run/{run_id}")
def get_run_status(run_id: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(None, authorization)
    run = next((row for row in load_runs() if row.get("run_id") == run_id and row.get("user_email") == email), None)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/update")
def update_workflow(req: UpdateWorkflowRequest, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(req.user_email, authorization)
    workflows = load_workflows()
    for workflow in workflows:
        if workflow.get("workflow_id") == req.workflow_id and workflow.get("user_email") == email:
            if req.name:
                workflow["name"] = req.name
            if req.description is not None:
                workflow["description"] = req.description
            if req.steps is not None:
                workflow["steps"] = _normalize_steps(req.steps)
            if req.status:
                workflow["status"] = req.status
            workflow["updated_at"] = _now()
            rewrite_workflows(workflows)
            return {"message": "Workflow updated", "workflow": workflow}
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.delete("/delete/{workflow_id}/{user_email}")
def delete_workflow(workflow_id: str, user_email: str, authorization: str | None = Header(None)) -> dict:
    email = resolve_scoped_user_email(user_email, authorization)
    workflows = load_workflows()
    for workflow in workflows:
        if workflow.get("workflow_id") == workflow_id and workflow.get("user_email") == email:
            workflow["deleted"] = True
            workflow["deleted_at"] = _now()
            rewrite_workflows(workflows)
            return {"message": "Workflow deleted"}
    raise HTTPException(status_code=404, detail="Workflow not found")
