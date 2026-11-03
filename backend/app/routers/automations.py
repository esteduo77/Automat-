from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Workflow, WorkflowSchedule
from backend.app.services.workflow_engine import validate_graph

router = APIRouter(prefix="/automations", tags=["automations"])

class ScheduleCreate(BaseModel):
    interval_seconds: int = Field(ge=60, le=31_536_000)

@router.get("")
def list_schedules(db: Session = Depends(get_db)):
    rows = db.scalars(select(WorkflowSchedule).order_by(WorkflowSchedule.created_at.desc())).all()
    return [{"id": x.id, "workflow_id": x.workflow_id, "enabled": x.enabled,
             "interval_seconds": x.interval_seconds, "next_run_at": x.next_run_at} for x in rows]

@router.post("/workflows/{workflow_id}/schedule", status_code=201)
def create_schedule(workflow_id: str, payload: ScheduleCreate, db: Session = Depends(get_db)):
    workflow = db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow introuvable.")
    errors = validate_graph(workflow.graph)
    if errors:
        raise HTTPException(422, detail=errors)
    workflow.status = "active"
    now = datetime.now(timezone.utc)
    schedule = WorkflowSchedule(id=str(uuid4()), workflow_id=workflow.id, enabled=True,
        interval_seconds=payload.interval_seconds, next_run_at=now + timedelta(seconds=payload.interval_seconds))
    db.add(schedule); db.commit(); db.refresh(schedule)
    return {"id": schedule.id, "workflow_id": schedule.workflow_id, "enabled": schedule.enabled,
            "interval_seconds": schedule.interval_seconds, "next_run_at": schedule.next_run_at}

@router.post("/{schedule_id}/pause")
def pause_schedule(schedule_id: str, db: Session = Depends(get_db)):
    schedule = db.get(WorkflowSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Déclencheur introuvable.")
    schedule.enabled = False; db.commit()
    return {"id": schedule.id, "enabled": False}

@router.post("/{schedule_id}/resume")
def resume_schedule(schedule_id: str, db: Session = Depends(get_db)):
    schedule = db.get(WorkflowSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Déclencheur introuvable.")
    schedule.enabled = True
    schedule.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=schedule.interval_seconds)
    db.commit()
    return {"id": schedule.id, "enabled": True, "next_run_at": schedule.next_run_at}
