"""JWT authentication and password hashing."""
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models import User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(password, hashed)
    except Exception:
        return False

def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)},
                      settings.jwt_secret, algorithm="HS256")

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401, "Authentification requise.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(401, "Session invalide ou expirée.", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(401, "Compte indisponible.")
    return user
