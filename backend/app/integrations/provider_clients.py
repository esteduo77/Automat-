"""Small, server-side Google and Microsoft Graph clients for connected accounts."""
import base64
"""Small, server-side Google and Microsoft Graph clients for connected accounts."""
import json
from datetime import datetime, timedelta, timezone
import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.config import get_settings
from backend.app.models import OAuthConnection

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

def _cipher():
    key = get_settings().oauth_encryption_key
    if not key:
        raise RuntimeError("OAUTH_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode())

async def _access_token(db: Session, provider: str, user_id: str) -> str:
    connection = db.scalar(select(OAuthConnection).where(OAuthConnection.provider == provider, OAuthConnection.user_id == user_id))
    if not connection:
        raise RuntimeError(f"{provider} account is not connected")
    tokens = json.loads(_cipher().decrypt(connection.encrypted_tokens.encode()).decode())
    expires_at = float(tokens.get("obtained_at", 0)) + float(tokens.get("expires_in", 0))
    if tokens.get("refresh_token") and expires_at < datetime.now(timezone.utc).timestamp() + 90:
        settings = get_settings()
        if provider == "google":
            data = {"client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
                    "refresh_token": tokens["refresh_token"], "grant_type": "refresh_token"}
            endpoint = GOOGLE_TOKEN_URL
        else:
            data = {"client_id": settings.microsoft_client_id, "client_secret": settings.microsoft_client_secret,
                    "refresh_token": tokens["refresh_token"], "grant_type": "refresh_token",
                    "scope": "openid profile email offline_access User.Read Mail.ReadBasic Mail.Send Files.ReadWrite"}
            endpoint = MS_TOKEN_URL
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(endpoint, data=data)
            response.raise_for_status()
            refreshed = response.json()
        refreshed.setdefault("refresh_token", tokens["refresh_token"])
        refreshed["obtained_at"] = datetime.now(timezone.utc).timestamp()
        tokens = refreshed
        connection.encrypted_tokens = _cipher().encrypt(json.dumps(tokens).encode()).decode()
        db.commit()
    if not tokens.get("access_token"):
        raise RuntimeError(f"{provider} access token is unavailable; reconnect the account")
    return tokens["access_token"]

async def google_action(db: Session, action: str, config: dict, context: dict, user_id: str) -> dict:
    token = await _access_token(db, "google", user_id)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30) as client:

        if action == "google.gmail.send":
            from email.message import EmailMessage
            message = EmailMessage()
            recipient = str(config.get("to") or "")
            if not recipient or "@" not in recipient:
                raise ValueError("Adresse destinataire invalide.")
            message["To"] = recipient
            message["Subject"] = str(config.get("subject") or "")[:250]
            message.set_content(str(config.get("body") or context.get("text") or "")[:100000])
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
            response = await client.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                json={"raw": raw}, headers=headers)
            response.raise_for_status()
            return {"sent": True, "message_id": response.json().get("id")}
        if action in ("google.drive.create", "google.drive.update"):
            name = str(config.get("name") or "").strip()
            content = str(config.get("content") or context.get("text") or "")
            if not name or "/" in name or chr(92) in name or name in (".", ".."):
                raise ValueError("Nom de fichier invalide.")
            mime = str(config.get("mime_type") or "text/plain")
            if action == "google.drive.create":
                boundary = "automationhub-boundary"
                body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" +
                    json.dumps({"name": name, "mimeType": mime}) +
                    f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n" + content +
                    f"\r\n--{boundary}--")
                response = await client.post("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                    headers={**headers, "Content-Type": f"multipart/related; boundary={boundary}"}, content=body.encode())
            else:
                import re
                file_id = str(config.get("file_id") or "")
                if not re.fullmatch("[A-Za-z0-9_-]+", file_id):
                    raise ValueError("file_id Drive invalide.")
                response = await client.patch(f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media",
                    headers={**headers, "Content-Type": mime}, content=content.encode())
            response.raise_for_status()
            return {"file": response.json()}
        if action == "google.gmail.search":
            query = str(config.get("query") or "newer_than:30d")[:500]
            response = await client.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",
                params={"q": query, "maxResults": min(max(int(config.get("limit", 10)), 1), 50)}, headers=headers)
            response.raise_for_status()
            payload = response.json()
            messages = []
            for item in payload.get("messages", [])[:50]:
                detail = await client.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]}, headers=headers)
                detail.raise_for_status()
                msg = detail.json()
                headers_list = msg.get("payload", {}).get("headers", [])
                messages.append({"id": msg.get("id"), "thread_id": msg.get("threadId"),
                    "snippet": msg.get("snippet", ""),
                    "headers": {h.get("name", "").lower(): h.get("value", "") for h in headers_list}})
            return {"messages": messages, "count": len(messages), "next_page_token": payload.get("nextPageToken")}
        if action == "google.drive.search":
            query = str(config.get("query") or "trashed = false")[:500]
            response = await client.get("https://www.googleapis.com/drive/v3/files",
                params={"q": query, "pageSize": min(max(int(config.get("limit", 20)), 1), 100),
                        "fields": "files(id,name,mimeType,modifiedTime,webViewLink),nextPageToken"}, headers=headers)
            response.raise_for_status()
            return response.json()
    raise ValueError(f"Unsupported Google action: {action}")

async def microsoft_action(db: Session, action: str, config: dict, context: dict, user_id: str) -> dict:
    token = await _access_token(db, "microsoft", user_id)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    limit = min(max(int(config.get("limit", 10)), 1), 50)
    async with httpx.AsyncClient(timeout=30) as client:

        if action == "microsoft.mail.send":
            recipient = str(config.get("to") or "")
            if not recipient or "@" not in recipient: raise ValueError("Adresse destinataire invalide.")
            payload = {"message": {"subject": str(config.get("subject") or "")[:250],
                "body": {"contentType": "Text", "content": str(config.get("body") or context.get("text") or "")[:100000]},
                "toRecipients": [{"emailAddress": {"address": recipient}}]}}
            response = await client.post("https://graph.microsoft.com/v1.0/me/sendMail", json=payload, headers=headers)
            response.raise_for_status()
            return {"sent": True}
        if action in ("microsoft.drive.create", "microsoft.drive.update"):
            from urllib.parse import quote
            path = str(config.get("path") or config.get("name") or "").strip().strip("/")
            if not path or ".." in path.split("/") or chr(92) in path:
                raise ValueError("Chemin OneDrive invalide.")
            content = str(config.get("content") or context.get("text") or "")
            encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
            url = "https://graph.microsoft.com/v1.0/me/drive/root:/" + encoded_path + ":/content"
            response = await client.put(url, content=content.encode(), headers={**headers, "Content-Type": "text/plain; charset=utf-8"})
            response.raise_for_status()
            return {"file": response.json()}
        if action == "microsoft.mail.search":
            params = {"$top": limit, "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead",
                      "$orderby": "receivedDateTime desc"}
            query = str(config.get("query") or "").strip()
            if query:
                params["$search"] = '"' + query.replace('"', "")[:200] + '"'
                headers["ConsistencyLevel"] = "eventual"
            response = await client.get("https://graph.microsoft.com/v1.0/me/messages", params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        if action == "microsoft.drive.search":
            query = str(config.get("query") or "").strip()
            if query:
                url = "https://graph.microsoft.com/v1.0/me/drive/root/search(q='" + query.replace("'", "''")[:200] + "')"
            else:
                url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
            response = await client.get(url, params={"$top": limit, "$select": "id,name,file,folder,lastModifiedDateTime,webUrl"}, headers=headers)
            response.raise_for_status()
            return response.json()
    raise ValueError(f"Unsupported Microsoft action: {action}")
