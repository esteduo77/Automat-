"""Independent database-backed worker and interval scheduler."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, update
from backend.app.database import SessionLocal
from backend.app.config import get_settings
from backend.app.models import Workflow, WorkflowRun, WorkflowSchedule
from backend.app.services.workflow_engine import execute_run, validate_graph

logger = logging.getLogger(__name__)

async def _execute_queued(run_id: str) -> None:
    db = SessionLocal()
    try:
        # Atomic compare-and-set prevents two worker processes claiming the same run.
        claimed = db.execute(update(WorkflowRun).where(
            WorkflowRun.id == run_id, WorkflowRun.status == "queued"
        ).values(status="running"))
        if claimed.rowcount != 1:
            db.rollback()
            return
        db.commit()
        run = db.get(WorkflowRun, run_id)
        if not run:
            return
        workflow = db.get(Workflow, run.workflow_id)
        if not workflow:
            run.status = "failed"; run.output_data = {"error": "Workflow not found"}
            run.finished_at = datetime.now(timezone.utc); db.commit(); return
        await execute_run(db, run, workflow)
    except Exception:
        logger.exception("Background workflow run failed: %s", run_id)
        db.rollback()
        run = db.get(WorkflowRun, run_id)
        if run:
            run.status = "failed"; run.finished_at = datetime.now(timezone.utc); db.commit()
    finally:
        db.close()

async def _enqueue_due_schedules() -> None:
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        schedules = db.scalars(select(WorkflowSchedule).where(
            WorkflowSchedule.enabled.is_(True), WorkflowSchedule.next_run_at <= now
        ).limit(25)).all()
        for schedule in schedules:
            next_time = now + timedelta(seconds=schedule.interval_seconds)
            claimed = db.execute(update(WorkflowSchedule).where(
                WorkflowSchedule.id == schedule.id,
                WorkflowSchedule.enabled.is_(True),
                WorkflowSchedule.next_run_at <= now
            ).values(next_run_at=next_time))
            if claimed.rowcount != 1:
                continue
            workflow = db.get(Workflow, schedule.workflow_id)
            if workflow and workflow.status == "active" and not validate_graph(workflow.graph):
                run = WorkflowRun(id=str(uuid4()), workflow_id=workflow.id, workflow_version=workflow.version,
                    status="queued", input_data={"trigger": "schedule", "scheduled_at": now.isoformat()},
                    graph_snapshot=workflow.graph)
                db.add(run)
        db.commit()
    except Exception:
        db.rollback(); logger.exception("Unable to enqueue scheduled workflows")
    finally:
        db.close()

async def worker_loop(stop: asyncio.Event) -> None:
    """Polls queued work; conditional updates make queue and schedule claims atomic."""
    while not stop.is_set():
        db = SessionLocal()
        try:
            queued = db.scalars(select(WorkflowRun).where(WorkflowRun.status == "queued")
                                .order_by(WorkflowRun.started_at).limit(5)).all()
            run_ids = [item.id for item in queued]
        finally:
            db.close()
        await _enqueue_due_schedules()
        for run_id in run_ids:
            await _execute_queued(run_id)
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(0.5, get_settings().worker_poll_seconds))
        except asyncio.TimeoutError:
            pass
