"""Lease-based worker with crash recovery and bounded retries."""
import asyncio
import logging
import os
import httpx
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import or_, select, update
from backend.app.database import SessionLocal
from backend.app.config import get_settings
from backend.app.integrations.provider_clients import _access_token
from backend.app.models import NodeRun, ProviderSubscription, Workflow, WorkflowRun, WorkflowSchedule
from backend.app.services.workflow_engine import execute_run, validate_graph

logger = logging.getLogger(__name__)
LEASE_SECONDS = 180
HEARTBEAT_SECONDS = 45
WORKER_ID = f"{os.getenv('HOSTNAME', 'worker')}:{uuid4().hex[:12]}"

def utcnow():
    return datetime.now(timezone.utc)

async def _heartbeat(run_id: str, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_SECONDS)
            break
        except asyncio.TimeoutError:
            db = SessionLocal()
            try:
                db.execute(update(WorkflowRun).where(
                    WorkflowRun.id == run_id, WorkflowRun.status == "running",
                    WorkflowRun.worker_id == WORKER_ID
                ).values(lease_expires_at=utcnow() + timedelta(seconds=LEASE_SECONDS)))
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Unable to renew worker lease for run %s", run_id)
            finally:
                db.close()

async def _execute_queued(run_id: str) -> None:
    db = SessionLocal()
    try:
        now = utcnow()
        claimed = db.execute(update(WorkflowRun).where(
            WorkflowRun.id == run_id, WorkflowRun.status == "queued",
            or_(WorkflowRun.available_at.is_(None), WorkflowRun.available_at <= now)
        ).values(status="running", worker_id=WORKER_ID,
                 lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
                 attempts=WorkflowRun.attempts + 1, finished_at=None))
        if claimed.rowcount != 1:
            db.rollback()
            return
        db.commit()
        run = db.get(WorkflowRun, run_id)
        if not run:
            return
        workflow = db.get(Workflow, run.workflow_id)
        if not workflow:
            run.status = "failed"; run.last_error = "Workflow not found"
            run.finished_at = utcnow(); run.worker_id = None; run.lease_expires_at = None
            db.commit(); return
        if not workflow.owner_id:
            run.status = "failed"
            run.output_data = {"error": "Workflow has no owner; transfer ownership before execution."}
            run.last_error = run.output_data["error"]
            run.finished_at = utcnow(); run.worker_id = None; run.lease_expires_at = None
            db.commit(); return
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(_heartbeat(run_id, heartbeat_stop))
        try:
            await execute_run(db, run, workflow)
        finally:
            heartbeat_stop.set()
            await heartbeat_task
            current = db.get(WorkflowRun, run_id)
            if current and current.worker_id == WORKER_ID:
                current.worker_id = None
                current.lease_expires_at = None
                db.commit()
    except Exception as exc:
        logger.exception("Background workflow run failed: %s", run_id)
        db.rollback()
        run = db.get(WorkflowRun, run_id)
        if run and run.status == "running" and run.worker_id == WORKER_ID:
            in_flight = db.scalar(select(NodeRun.id).where(
                NodeRun.run_id == run_id, NodeRun.status == "running").limit(1))
            run.last_error = str(exc)[:2000]
            run.worker_id = None; run.lease_expires_at = None
            if not in_flight and run.attempts < run.max_attempts:
                run.status = "queued"
                run.available_at = utcnow() + timedelta(seconds=min(300, 2 ** max(1, run.attempts)))
            else:
                run.status = "failed"; run.finished_at = utcnow()
            db.commit()
    finally:
        db.close()

async def _recover_expired_runs() -> None:
    now = utcnow()
    db = SessionLocal()
    try:
        expired = db.scalars(select(WorkflowRun).where(
            WorkflowRun.status == "running",
            WorkflowRun.lease_expires_at.is_not(None),
            WorkflowRun.lease_expires_at <= now
        ).limit(100)).all()
        for run in expired:
            in_flight = db.scalar(select(NodeRun.id).where(
                NodeRun.run_id == run.id, NodeRun.status == "running").limit(1))
            run.worker_id = None
            run.lease_expires_at = None
            run.last_error = "Worker lease expired; execution was interrupted."
            if in_flight:
                run.status = "failed"
                run.finished_at = now
                db.execute(update(NodeRun).where(
                    NodeRun.run_id == run.id, NodeRun.status == "running"
                ).values(status="failed", error="Worker interrupted during this step; external outcome is unknown.",
                         finished_at=now))
            elif run.attempts < run.max_attempts:
                run.status = "queued"
                run.available_at = now + timedelta(seconds=min(300, 2 ** max(1, run.attempts)))
            else:
                run.status = "failed"
                run.finished_at = now
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Unable to recover expired worker leases")
    finally:
        db.close()

async def _enqueue_due_schedules() -> None:
    now = utcnow()
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
            if workflow and workflow.owner_id and workflow.status == "active" and not validate_graph(workflow.graph):
                db.add(WorkflowRun(id=str(uuid4()), workflow_id=workflow.id, workflow_version=workflow.version,
                    status="queued", input_data={"_trigger_type": "schedule", "trigger": "schedule", "scheduled_at": now.isoformat()},
                    graph_snapshot=workflow.graph))
        db.commit()
    except Exception:
        db.rollback(); logger.exception("Unable to enqueue scheduled workflows")
    finally:
        db.close()


async def _renew_due_provider_subscriptions() -> None:
    """Renew provider channels before expiry; failures stay visible for operator action."""
    db = SessionLocal()
    now = utcnow()
    try:
        rows = db.scalars(select(ProviderSubscription).where(
            ProviderSubscription.enabled.is_(True),
            ProviderSubscription.expires_at.is_not(None),
            ProviderSubscription.expires_at <= now + timedelta(hours=24)
        ).limit(25)).all()
        for row in rows:
            try:
                provider = "google" if row.provider.startswith("google_") else "microsoft"
                token = await _access_token(db, provider, row.user_id)
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=25) as client:
                    if row.provider == "google_gmail":
                        settings = get_settings()
                        if not settings.google_pubsub_topic:
                            logger.error("Cannot renew Gmail watch: GOOGLE_PUBSUB_TOPIC is missing")
                            continue
                        response = await client.post(
                            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                            headers=headers, json={"topicName": settings.google_pubsub_topic, "labelIds": ["INBOX"]}
                        )
                        response.raise_for_status()
                        data = response.json()
                        row.cursor = str(data.get("historyId", row.cursor or ""))
                        row.expires_at = datetime.fromtimestamp(int(data["expiration"]) / 1000, timezone.utc)
                    elif row.provider == "google_drive":
                        settings = get_settings()
                        if not settings.public_base_url.startswith("https://") or not row.cursor:
                            logger.error("Cannot renew Drive channel: public URL or page cursor missing")
                            continue
                        channel_id = str(uuid4())
                        old_id, old_resource = row.subscription_id, row.resource_id
                        response = await client.post(
                            "https://www.googleapis.com/drive/v3/changes/watch",
                            params={"pageToken": row.cursor}, headers=headers,
                            json={"id": channel_id, "type": "web_hook",
                                  "address": settings.public_base_url.rstrip("/") + "/api/provider-events/google/drive",
                                  "token": row.client_state}
                        )
                        response.raise_for_status()
                        data = response.json()
                        row.subscription_id = channel_id
                        row.resource_id = str(data.get("resourceId", ""))
                        row.expires_at = datetime.fromtimestamp(int(data["expiration"]) / 1000, timezone.utc)
                        if old_resource:
                            try:
                                await client.post("https://www.googleapis.com/drive/v3/channels/stop",
                                                  headers=headers, json={"id": old_id, "resourceId": old_resource})
                            except Exception:
                                logger.warning("Old Drive channel could not be stopped; it will expire naturally")
                    elif row.provider == "microsoft":
                        expiry = now + timedelta(days=2)
                        response = await client.patch(
                            "https://graph.microsoft.com/v1.0/subscriptions/" + row.subscription_id,
                            headers=headers, json={"expirationDateTime": expiry.isoformat()}
                        )
                        response.raise_for_status()
                        data = response.json()
                        row.expires_at = datetime.fromisoformat(data["expirationDateTime"].replace("Z", "+00:00"))
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Unable to renew %s provider subscription %s", row.provider, row.id)
    finally:
        db.close()

async def worker_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        await _recover_expired_runs()
        await _renew_due_provider_subscriptions()
        db = SessionLocal()
        try:
            queued = db.scalars(select(WorkflowRun).where(
                WorkflowRun.status == "queued",
                or_(WorkflowRun.available_at.is_(None), WorkflowRun.available_at <= utcnow())
            ).order_by(WorkflowRun.started_at).limit(5)).all()
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
