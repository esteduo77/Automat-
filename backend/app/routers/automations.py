from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import User, Workflow, WorkflowSchedule
from backend.app.security import get_current_user
from backend.app.services.workflow_engine import validate_graph

router = APIRouter(prefix="/automations", tags=["automations"])
class ScheduleCreate(BaseModel):
    interval_seconds: int = Field(ge=60, le=31_536_000)

def owned_schedule(db, schedule_id, user):
    row = db.scalar(select(WorkflowSchedule).join(Workflow).where(
        WorkflowSchedule.id == schedule_id, Workflow.owner_id == user.id))
    if not row: raise HTTPException(404, "Déclencheur introuvable.")
    return row

@router.get("")
def list_schedules(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(WorkflowSchedule).join(Workflow).where(Workflow.owner_id==user.id).order_by(WorkflowSchedule.created_at.desc())).all()
    return [{"id":x.id,"workflow_id":x.workflow_id,"enabled":x.enabled,"interval_seconds":x.interval_seconds,"next_run_at":x.next_run_at} for x in rows]

@router.post("/workflows/{workflow_id}/schedule",status_code=201)
def create_schedule(workflow_id:str,payload:ScheduleCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    workflow=db.scalar(select(Workflow).where(Workflow.id==workflow_id,Workflow.owner_id==user.id))
    if not workflow:raise HTTPException(404,"Workflow introuvable.")
    errors=validate_graph(workflow.graph)
    if errors:raise HTTPException(422,detail=errors)
    workflow.status="active";now=datetime.now(timezone.utc)
    schedule=WorkflowSchedule(id=str(uuid4()),workflow_id=workflow.id,enabled=True,interval_seconds=payload.interval_seconds,next_run_at=now+timedelta(seconds=payload.interval_seconds))
    db.add(schedule);db.commit();db.refresh(schedule)
    return {"id":schedule.id,"workflow_id":schedule.workflow_id,"enabled":schedule.enabled,"interval_seconds":schedule.interval_seconds,"next_run_at":schedule.next_run_at}

@router.post("/{schedule_id}/pause")
def pause_schedule(schedule_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=owned_schedule(db,schedule_id,user);row.enabled=False;db.commit()
    return {"id":row.id,"enabled":False}

@router.post("/{schedule_id}/resume")
def resume_schedule(schedule_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=owned_schedule(db,schedule_id,user);row.enabled=True
    row.next_run_at=datetime.now(timezone.utc)+timedelta(seconds=row.interval_seconds);db.commit()
    return {"id":row.id,"enabled":True,"next_run_at":row.next_run_at}
