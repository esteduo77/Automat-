"""Native Google and Microsoft change-notification subscriptions."""
import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.integrations.provider_clients import _access_token
from backend.app.models import ProviderSubscription, User, Workflow, WorkflowRun
from backend.app.security import get_current_user
from backend.app.services.workflow_engine import validate_graph

router = APIRouter(prefix="/provider-events", tags=["native provider events"])


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def _queue_event(db: Session, subscription: ProviderSubscription, event: dict) -> None:
    workflow = db.scalar(select(Workflow).where(
        Workflow.id == subscription.workflow_id,
        Workflow.owner_id == subscription.user_id,
        Workflow.status == "active"
    ))
    if not workflow or validate_graph(workflow.graph):
        return
    db.add(WorkflowRun(
        id=str(uuid4()), workflow_id=workflow.id, workflow_version=workflow.version,
        status="queued",
        input_data={"_trigger_type": "webhook", "trigger": "provider_event",
                    "provider": subscription.provider, "resource": subscription.resource,
                    "event": event, "received_at": datetime.now(timezone.utc).isoformat()},
        graph_snapshot=workflow.graph
    ))


class SubscriptionRequest(BaseModel):
    workflow_id: str
    provider: str = Field(pattern="^(google_gmail|google_drive|microsoft)$")
    resource: str | None = None


@router.post("/subscriptions", status_code=201)
async def create_subscription(payload: SubscriptionRequest, user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    settings = get_settings()
    workflow = db.scalar(select(Workflow).where(
        Workflow.id == payload.workflow_id, Workflow.owner_id == user.id))
    if not workflow:
        raise HTTPException(404, "Workflow introuvable.")
    if workflow.status != "active":
        raise HTTPException(409, "Activez le workflow avant de créer un abonnement.")
    if validate_graph(workflow.graph):
        raise HTTPException(422, "Le graphe du workflow est invalide.")
    if not settings.public_base_url.startswith("https://"):
        raise HTTPException(503, "PUBLIC_BASE_URL doit être une URL HTTPS publique.")
    provider = payload.provider
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    try:
        token = await _access_token(db, "google" if provider.startswith("google_") else "microsoft", user.id)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=25) as client:
            if provider == "google_gmail":
                if not settings.google_pubsub_topic or not settings.google_pubsub_push_token:
                    raise HTTPException(503, "Configurez GOOGLE_PUBSUB_TOPIC et GOOGLE_PUBSUB_PUSH_TOKEN.")
                response = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                    headers=headers,
                    json={"topicName": settings.google_pubsub_topic, "labelIds": ["INBOX"]}
                )
                response.raise_for_status()
                data = response.json()
                subscription_id = "gmail:" + user.id
                expires = datetime.fromtimestamp(int(data["expiration"]) / 1000, timezone.utc)
                cursor = str(data.get("historyId", ""))
                resource_id = None
                resource = "gmail"
            elif provider == "google_drive":
                start = await client.get("https://www.googleapis.com/drive/v3/changes/startPageToken", headers=headers)
                start.raise_for_status()
                channel_id = str(uuid4())
                response = await client.post(
                    "https://www.googleapis.com/drive/v3/changes/watch",
                    params={"pageToken": start.json()["startPageToken"]},
                    headers=headers,
                    json={"id": channel_id, "type": "web_hook",
                          "address": settings.public_base_url.rstrip("/") + "/api/provider-events/google/drive",
                          "token": state}
                )
                response.raise_for_status()
                data = response.json()
                subscription_id = channel_id
                expires = datetime.fromtimestamp(int(data["expiration"]) / 1000, timezone.utc)
                cursor = str(start.json()["startPageToken"])
                resource_id = str(data.get("resourceId", ""))
                resource = "drive_changes"
            else:
                resource = payload.resource or "me/messages"
                if resource not in ("me/messages", "me/drive/root"):
                    raise HTTPException(422, "Ressource Microsoft non prise en charge.")
                expires = now + timedelta(days=2)
                callback = settings.public_base_url.rstrip("/") + "/api/provider-events/microsoft"
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/subscriptions",
                    headers=headers,
                    json={"changeType": "created,updated", "notificationUrl": callback,
                          "resource": resource, "expirationDateTime": expires.isoformat(),
                          "clientState": state}
                )
                response.raise_for_status()
                data = response.json()
                subscription_id = data["id"]
                expires = datetime.fromisoformat(data["expirationDateTime"].replace("Z", "+00:00"))
                cursor = None
                resource_id = None
        row = ProviderSubscription(
            id=str(uuid4()), user_id=user.id, workflow_id=workflow.id, provider=provider,
            resource=resource, subscription_id=subscription_id, client_state=state,
            expires_at=expires, cursor=cursor, resource_id=resource_id, enabled=True
        )
        db.add(row)
        db.commit()
        return {"id": row.id, "provider": provider, "resource": resource,
                "expires_at": expires, "status": "active"}
    except HTTPException:
        db.rollback()
        raise
    except httpx.HTTPStatusError as exc:
        db.rollback()
        raise HTTPException(502, f"Le fournisseur a refusé la création de l'abonnement (HTTP {exc.response.status_code}).")
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, "Impossible de créer l'abonnement fournisseur.") from exc


@router.get("/microsoft", response_class=PlainTextResponse)
async def microsoft_validation(validationToken: str | None = Query(default=None)):
    if validationToken is not None:
        return PlainTextResponse(validationToken)
    raise HTTPException(400, "Validation token absent.")


@router.post("/microsoft")
async def microsoft_notifications(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    notifications = payload.get("value", [])
    accepted = 0
    for item in notifications:
        subscription_id = item.get("subscriptionId")
        state = item.get("clientState")
        row = db.scalar(select(ProviderSubscription).where(
            ProviderSubscription.provider == "microsoft",
            ProviderSubscription.subscription_id == subscription_id,
            ProviderSubscription.client_state == state,
            ProviderSubscription.enabled.is_(True)
        ))
        if row:
            _queue_event(db, row, item)
            accepted += 1
    db.commit()
    return {"accepted": accepted}


@router.post("/google/gmail")
async def google_gmail_notification(request: Request, authorization: str = Header(default=""),
                                    db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.google_pubsub_audience or not settings.google_pubsub_service_account:
        raise HTTPException(503, "Identité OIDC Pub/Sub non configurée.")
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(authorization.removeprefix("Bearer "), GoogleAuthRequest(),
                                              audience=settings.google_pubsub_audience)
        if claims.get("email") != settings.google_pubsub_service_account or not claims.get("email_verified"):
            raise ValueError("Unexpected Pub/Sub service account")
    except Exception as exc:
        raise HTTPException(401, "Authentification Pub/Sub invalide.") from exc
    payload = await request.json()
    message = payload.get("message", {})
    try:
        data = json.loads(base64.b64decode(message.get("data", ""), validate=True))
    except Exception as exc:
        raise HTTPException(400, "Notification Pub/Sub invalide.") from exc
    email = str(data.get("emailAddress", "")).lower()
    rows = db.scalars(select(ProviderSubscription).where(
        ProviderSubscription.provider == "google_gmail",
        ProviderSubscription.enabled.is_(True)
    )).all()
    accepted = 0
    for row in rows:
        from backend.app.models import OAuthConnection
        connection = db.scalar(select(OAuthConnection).where(
            OAuthConnection.user_id == row.user_id, OAuthConnection.provider == "google"))
        if connection and connection.account_email.lower() == email:
            _queue_event(db, row, {"emailAddress": email, "historyId": data.get("historyId")})
            accepted += 1
    db.commit()
    return {"accepted": accepted}


@router.post("/google/drive")
async def google_drive_notification(
    x_goog_channel_id: str = Header(default=""),
    x_goog_channel_token: str = Header(default=""),
    x_goog_resource_state: str = Header(default=""),
    x_goog_resource_id: str = Header(default=""),
    db: Session = Depends(get_db)
):
    row = db.scalar(select(ProviderSubscription).where(
        ProviderSubscription.provider == "google_drive",
        ProviderSubscription.subscription_id == x_goog_channel_id,
        ProviderSubscription.client_state == x_goog_channel_token,
        ProviderSubscription.enabled.is_(True)
    ))
    if not row:
        raise HTTPException(404, "Canal Google Drive inconnu.")
    _queue_event(db, row, {"resourceState": x_goog_resource_state, "resourceId": x_goog_resource_id})
    db.commit()
    return {"accepted": True}
