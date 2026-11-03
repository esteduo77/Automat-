from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Approval, NodeRun, User, Workflow, WorkflowRun
from backend.app.schemas import ApprovalDecision, RunRequest, WorkflowGraph
from backend.app.security import get_current_user
from backend.app.services.workflow_engine import validate_graph

router = APIRouter(prefix="/workflows", tags=["workflows"])

def serialize_workflow(item):
    return {"id": item.id, "name": item.name, "status": item.status, "version": item.version,
        "graph": item.graph, "created_at": item.created_at, "updated_at": item.updated_at}

def serialize_run(run):
    return {"id": run.id, "workflow_id": run.workflow_id, "workflow_version": run.workflow_version,
        "status": run.status, "input": run.input_data, "output": run.output_data,
        "started_at": run.started_at, "finished_at": run.finished_at,
        "steps": [{"id": s.id, "node_id": s.node_id, "type": s.node_type, "status": s.status,
            "output": s.output_data, "error": s.error, "started_at": s.started_at, "finished_at": s.finished_at} for s in run.steps],
        "approvals": [{"id": a.id, "node_id": a.node_id, "status": a.status, "summary": a.summary,
            "comment": a.decision_comment} for a in run.approvals]}

def owned_workflow(db, workflow_id, user):
    item = db.scalar(select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user.id))
    if not item: raise HTTPException(404, "Workflow introuvable.")
    return item

@router.post("", status_code=201)
def create_workflow(payload: WorkflowGraph, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    graph = payload.model_dump(); errors = validate_graph(graph)
    if errors: raise HTTPException(422, detail=errors)
    item = Workflow(id=str(uuid4()), owner_id=user.id, name=payload.name, graph=graph)
    db.add(item); db.commit(); db.refresh(item)
    return serialize_workflow(item)

@router.get("")
def list_workflows(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Workflow).where(Workflow.owner_id == user.id).order_by(Workflow.updated_at.desc())).all()
    return [serialize_workflow(item) for item in rows]

@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_workflow(owned_workflow(db, workflow_id, user))

@router.put("/{workflow_id}")
def update_workflow(workflow_id: str, payload: WorkflowGraph, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_workflow(db, workflow_id, user)
    graph = payload.model_dump(); errors = validate_graph(graph)
    if errors: raise HTTPException(422, detail=errors)
    item.name = payload.name; item.graph = graph; item.version += 1; item.status = "draft"
    db.commit(); db.refresh(item)
    return serialize_workflow(item)

@router.post("/{workflow_id}/validate")
def validate_workflow(workflow_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_workflow(db, workflow_id, user)
    errors = validate_graph(item.graph)
    return {"valid": not errors, "errors": errors}

@router.post("/{workflow_id}/activate")
def activate_workflow(workflow_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_workflow(db, workflow_id, user)
    errors = validate_graph(item.graph)
    if errors: raise HTTPException(422, detail=errors)
    item.status = "active"; db.commit()
    return serialize_workflow(item)

@router.post("/{workflow_id}/runs", status_code=202)
def run_workflow(workflow_id: str, payload: RunRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_workflow(db, workflow_id, user)
    errors = validate_graph(item.graph)
    if errors: raise HTTPException(422, detail=errors)
    run = WorkflowRun(id=str(uuid4()), workflow_id=item.id, workflow_version=item.version,
        status="queued", input_data=payload.input, graph_snapshot=item.graph)
    db.add(run); db.commit(); db.refresh(run)
    return serialize_run(run)

@router.get("/runs/{run_id}")
def get_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.scalar(select(WorkflowRun).join(Workflow).where(WorkflowRun.id == run_id, Workflow.owner_id == user.id))
    if not run: raise HTTPException(404, "Exécution introuvable.")
    return serialize_run(run)

@router.get("/{workflow_id}/runs")
def list_runs(workflow_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_workflow(db, workflow_id, user)
    runs = db.scalars(select(WorkflowRun).where(WorkflowRun.workflow_id == item.id).order_by(WorkflowRun.started_at.desc())).all()
    return [serialize_run(run) for run in runs]

@router.post("/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, payload: ApprovalDecision, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    approval = db.scalar(select(Approval).join(WorkflowRun).join(Workflow).where(
        Approval.id == approval_id, Workflow.owner_id == user.id))
    if not approval: raise HTTPException(404, "Approbation introuvable.")
    if approval.status != "pending": raise HTTPException(409, "Cette approbation a déjà été traitée.")
    approval.status = "approved" if payload.decision == "approve" else "rejected"
    approval.decision_comment = payload.comment; approval.decided_at = datetime.now(timezone.utc)
    run = db.get(WorkflowRun, approval.run_id)
    if payload.decision == "reject":
        run.status = "rejected"; run.finished_at = datetime.now(timezone.utc); db.commit()
        return serialize_run(run)
    # Keep the paused node pending: the worker re-runs it and checks the approved record.
    run.status = "queued"; db.commit()
    return serialize_run(run)
