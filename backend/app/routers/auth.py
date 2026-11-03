from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import User
from backend.app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

def _public_user(user: User):
    return {"id": user.id, "email": user.email, "created_at": user.created_at}

@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Cette adresse e-mail possède déjà un compte.")
    user = User(id=str(uuid4()), email=email, password_hash=hash_password(payload.password), is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": _public_user(user)}

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(401, "Adresse e-mail ou mot de passe incorrect.")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": _public_user(user)}

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _public_user(user)
