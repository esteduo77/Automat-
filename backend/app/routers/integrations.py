import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models import OAuthConnection, OAuthState

router = APIRouter(prefix="/integrations", tags=["integrations"])
GOOGLE_SCOPES = "openid email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive.metadata.readonly"
MICROSOFT_SCOPES = "openid profile email offline_access User.Read Mail.ReadBasic"
PROVIDERS = {
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": GOOGLE_SCOPES,
        "client_id_attr": "google_client_id",
        "client_secret_attr": "google_client_secret",
    },
    "microsoft": {
        "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo": "https://graph.microsoft.com/v1.0/me",
        "scope": MICROSOFT_SCOPES,
        "client_id_attr": "microsoft_client_id",
        "client_secret_attr": "microsoft_client_secret",
    },
}

def token_cipher() -> Fernet:
    key = get_settings().oauth_encryption_key
    if not key:
        raise HTTPException(503, "Configurez OAUTH_ENCRYPTION_KEY avec une clé Fernet avant d'activer OAuth.")
    try: return Fernet(key.encode())
    except Exception as exc: raise HTTPException(500, "OAUTH_ENCRYPTION_KEY doit être une clé Fernet valide.") from exc

@router.get("")
def integration_status(db: Session = Depends(get_db)):
    settings = get_settings()
    connections = db.scalars(select(OAuthConnection)).all()
    by_provider = {item.provider: item for item in connections}
    return {
        provider: {
            "configured": bool(getattr(settings, cfg["client_id_attr"]) and getattr(settings, cfg["client_secret_attr"])),
            "connected": provider in by_provider,
            "account": by_provider[provider].account_email if provider in by_provider else None,
            "scopes": cfg["scope"].split(),
        }
        for provider, cfg in PROVIDERS.items()
    }

@router.get("/{provider}/connect")
def connect_provider(provider: str, db: Session = Depends(get_db)):
    if provider not in PROVIDERS: raise HTTPException(404, "Fournisseur non pris en charge.")
    settings = get_settings(); cfg = PROVIDERS[provider]
    client_id = getattr(settings, cfg["client_id_attr"])
    client_secret = getattr(settings, cfg["client_secret_attr"])
    if not client_id or not client_secret: raise HTTPException(503, f"Les identifiants OAuth {provider} ne sont pas configurés.")
    token_cipher()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    db.add(OAuthState(state=state, provider=provider, code_verifier=verifier, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    redirect_uri = f"{settings.oauth_redirect_base.rstrip('/')}/api/integrations/{provider}/callback"
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": cfg["scope"], "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256", "prompt": "consent",
    }
    if provider == "google": params["access_type"] = "offline"
    return RedirectResponse(f"{cfg['authorize']}?{urlencode(params)}")

@router.get("/{provider}/callback")
async def oauth_callback(provider: str, code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    if provider not in PROVIDERS: raise HTTPException(404, "Fournisseur non pris en charge.")
    saved = db.get(OAuthState, state)
    if not saved or saved.provider != provider or (saved.expires_at.replace(tzinfo=timezone.utc) if saved.expires_at.tzinfo is None else saved.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(400, "État OAuth invalide ou expiré.")
    cfg = PROVIDERS[provider]; settings = get_settings()
    redirect_uri = f"{settings.oauth_redirect_base.rstrip('/')}/api/integrations/{provider}/callback"
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(cfg["token"], data={
            "client_id": getattr(settings, cfg["client_id_attr"]),
            "client_secret": getattr(settings, cfg["client_secret_attr"]),
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "code_verifier": saved.code_verifier,
        }, headers={"Accept": "application/json"})
        if token_response.status_code >= 400: raise HTTPException(400, f"Échange OAuth refusé par {provider}.")
        tokens = token_response.json()
        user_response = await client.get(cfg["userinfo"], params={"$select": "mail,userPrincipalName,displayName"} if provider == "microsoft" else None, headers={"Authorization": "Bearer " + tokens["access_token"]})
        if user_response.status_code >= 400: raise HTTPException(400, "Impossible de lire le profil du compte connecté.")
        profile = user_response.json()
    email = profile.get("email") or profile.get("userPrincipalName") or profile.get("mail")
    if not email: raise HTTPException(400, "Le fournisseur n'a pas retourné d'adresse de compte.")
    cipher = token_cipher()
    encrypted = cipher.encrypt(json.dumps(tokens).encode()).decode()
    existing = db.scalar(select(OAuthConnection).where(OAuthConnection.provider == provider))
    if existing:
        existing.account_email = email; existing.encrypted_tokens = encrypted
    else:
        db.add(OAuthConnection(id=str(uuid4()), provider=provider, account_email=email, encrypted_tokens=encrypted))
    db.delete(saved); db.commit()
    return RedirectResponse(f"{settings.frontend_base_url.rstrip('/')}/?integration={provider}&connected=1")

@router.delete("/{provider}")
def disconnect_provider(provider: str, db: Session = Depends(get_db)):
    if provider not in PROVIDERS: raise HTTPException(404, "Fournisseur non pris en charge.")
    existing = db.scalar(select(OAuthConnection).where(OAuthConnection.provider == provider))
    if existing: db.delete(existing); db.commit()
    return {"provider": provider, "connected": False}
