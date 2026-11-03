"""Authenticated event ingress for external provider webhook adapters."""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import User, WebhookEndpoint, Workflow, WorkflowRun
from backend.app.security import get_current_user
from backend.app.services.workflow_engine import validate_graph

router = APIRouter(prefix="/webhooks", tags=["event triggers"])

@router.post("/{endpoint_id}")
async def receive_event(endpoint_id: str, request: Request, x_automation_signature: str = Header(default=""),
                        db: Session = Depends(get_db)):
    endpoint = db.get(WebhookEndpoint, endpoint_id)
    if not endpoint or not endpoint.enabled:
        raise HTTPException(404, "Webhook inconnu ou désactivé.")
    raw = await request.body()
    expected = hmac.new(endpoint.secret.encode(), raw, hashlib.sha256).hexdigest()
    supplied = x_automation_signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, "Signature webhook invalide.")
    try:
        event = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Le corps webhook doit être du JSON valide.")
    workflow = db.get(Workflow, endpoint.workflow_id)
    if not workflow or workflow.status != "active":
        raise HTTPException(404, "Workflow actif introuvable.")
    errors = validate_graph(workflow.graph)
    if errors:
        raise HTTPException(422, detail=errors)
    run = WorkflowRun(id=str(uuid4()), workflow_id=workflow.id, workflow_version=workflow.version,
        status="queued", input_data={"trigger": "webhook", "event": event, "received_at": datetime.now(timezone.utc).isoformat()},
        graph_snapshot=workflow.graph)
    db.add(run); db.commit()
    return {"accepted": True, "run_id": run.id, "status": run.status}

@router.post("/workflows/{workflow_id}/endpoint")
def create_webhook_endpoint(workflow_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workflow = db.scalar(select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user.id))
    if not workflow:
        raise HTTPException(404, "Workflow introuvable.")
    secret = __import__("secrets").token_urlsafe(48)
    endpoint = WebhookEndpoint(id=str(uuid4()), workflow_id=workflow.id, secret=secret, enabled=True)
    db.add(endpoint); db.commit()
    return {"id": endpoint.id, "secret": secret, "path": f"/api/webhooks/{endpoint.id}",
            "signature_header": "X-Automation-Signature: sha256=<HMAC-SHA256 du corps avec le secret>"}
