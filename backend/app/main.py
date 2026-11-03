from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import get_settings
from backend.app.database import Base, engine
from backend.app import models
from backend.app.routers.health import router as health_router
from backend.app.routers.workflows import router as workflows_router
from backend.app.routers.integrations import router as integrations_router
from backend.app.routers.automations import router as automations_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.webhooks import router as webhooks_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.4.0",
    description="A secure, extensible automation hub.")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Automation-Signature"])

@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(workflows_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(automations_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "docs": "/docs",
            "worker": "separate-process: python -m backend.app.worker"}
