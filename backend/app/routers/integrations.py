import base64, hashlib, json, secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models import OAuthConnection, OAuthState, User
from backend.app.security import get_current_user

router = APIRouter(prefix="/integrations", tags=["integrations"])
GOOGLE_SCOPES = "openid email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.metadata.readonly"
MICROSOFT_SCOPES = "openid profile email offline_access User.Read Mail.ReadBasic Mail.Send Files.ReadWrite"
PROVIDERS = {
 "google":{"authorize":"https://accounts.google.com/o/oauth2/v2/auth","token":"https://oauth2.googleapis.com/token","userinfo":"https://openidconnect.googleapis.com/v1/userinfo","scope":GOOGLE_SCOPES,"client_id_attr":"google_client_id","client_secret_attr":"google_client_secret"},
 "microsoft":{"authorize":"https://login.microsoftonline.com/common/oauth2/v2.0/authorize","token":"https://login.microsoftonline.com/common/oauth2/v2.0/token","userinfo":"https://graph.microsoft.com/v1.0/me","scope":MICROSOFT_SCOPES,"client_id_attr":"microsoft_client_id","client_secret_attr":"microsoft_client_secret"}
}
def token_cipher():
 key=get_settings().oauth_encryption_key
 if not key: raise HTTPException(503,"Configurez OAUTH_ENCRYPTION_KEY.")
 try:return Fernet(key.encode())
 except Exception as exc: raise HTTPException(500,"Clé Fernet invalide.") from exc

@router.get("")
def integration_status(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 settings=get_settings()
 connections=db.scalars(select(OAuthConnection).where(OAuthConnection.user_id==user.id)).all()
 by_provider={x.provider:x for x in connections}
 return {p:{"configured":bool(getattr(settings,c["client_id_attr"]) and getattr(settings,c["client_secret_attr"])),"connected":p in by_provider,"account":by_provider[p].account_email if p in by_provider else None,"scopes":c["scope"].split()} for p,c in PROVIDERS.items()}

@router.get("/{provider}/connect")
def connect_provider(provider:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 if provider not in PROVIDERS: raise HTTPException(404,"Fournisseur non pris en charge.")
 settings=get_settings(); cfg=PROVIDERS[provider]
 if not getattr(settings,cfg["client_id_attr"]) or not getattr(settings,cfg["client_secret_attr"]): raise HTTPException(503,f"Identifiants OAuth {provider} non configurés.")
 token_cipher()
 state=secrets.token_urlsafe(32); verifier=secrets.token_urlsafe(64)
 challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
 db.add(OAuthState(state=state,user_id=user.id,provider=provider,code_verifier=verifier,expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)));db.commit()
 redirect_uri=f"{settings.oauth_redirect_base.rstrip('/')}/api/integrations/{provider}/callback"
 params={"client_id":getattr(settings,cfg["client_id_attr"]),"redirect_uri":redirect_uri,"response_type":"code","scope":cfg["scope"],"state":state,"code_challenge":challenge,"code_challenge_method":"S256","prompt":"consent"}
 if provider=="google":params["access_type"]="offline"
 return {"authorization_url": f"{cfg['authorize']}?{urlencode(params)}"}

@router.get("/{provider}/callback")
async def oauth_callback(provider:str,code:str=Query(...),state:str=Query(...),db:Session=Depends(get_db)):
 if provider not in PROVIDERS:raise HTTPException(404,"Fournisseur non pris en charge.")
 saved=db.get(OAuthState,state)
 expiry=(saved.expires_at.replace(tzinfo=timezone.utc) if saved and saved.expires_at.tzinfo is None else saved.expires_at) if saved else None
 if not saved or saved.provider!=provider or not saved.user_id or not expiry or expiry<datetime.now(timezone.utc):raise HTTPException(400,"État OAuth invalide ou expiré.")
 cfg=PROVIDERS[provider];settings=get_settings();redirect_uri=f"{settings.oauth_redirect_base.rstrip('/')}/api/integrations/{provider}/callback"
 async with httpx.AsyncClient(timeout=20) as client:
  tr=await client.post(cfg["token"],data={"client_id":getattr(settings,cfg["client_id_attr"]),"client_secret":getattr(settings,cfg["client_secret_attr"]),"grant_type":"authorization_code","code":code,"redirect_uri":redirect_uri,"code_verifier":saved.code_verifier})
  if tr.status_code>=400:raise HTTPException(400,f"Échange OAuth refusé par {provider}.")
  tokens=tr.json();tokens["obtained_at"]=datetime.now(timezone.utc).timestamp()
  ur=await client.get(cfg["userinfo"],params={"$select":"mail,userPrincipalName,displayName"} if provider=="microsoft" else None,headers={"Authorization":"Bearer "+tokens["access_token"]})
  if ur.status_code>=400:raise HTTPException(400,"Impossible de lire le profil connecté.")
  profile=ur.json()
 email=profile.get("email") or profile.get("userPrincipalName") or profile.get("mail")
 if not email:raise HTTPException(400,"Adresse de compte non retournée.")
 existing=db.scalar(select(OAuthConnection).where(OAuthConnection.provider==provider,OAuthConnection.user_id==saved.user_id))
 encrypted=token_cipher().encrypt(json.dumps(tokens).encode()).decode()
 if existing:existing.account_email=email;existing.encrypted_tokens=encrypted
 else:db.add(OAuthConnection(id=str(uuid4()),user_id=saved.user_id,provider=provider,account_email=email,encrypted_tokens=encrypted))
 db.delete(saved);db.commit()
 return RedirectResponse(f"{settings.frontend_base_url.rstrip('/')}/?integration={provider}&connected=1")

@router.delete("/{provider}")
def disconnect_provider(provider:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 if provider not in PROVIDERS:raise HTTPException(404,"Fournisseur non pris en charge.")
 existing=db.scalar(select(OAuthConnection).where(OAuthConnection.provider==provider,OAuthConnection.user_id==user.id))
 if existing:db.delete(existing);db.commit()
 return {"provider":provider,"connected":False}
