from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from cryptography.fernet import Fernet
from backend.app.config import get_settings
from backend.app.database import Base, engine
from backend.app import models
from backend.app.routers.health import router as health_router
from backend.app.routers.workflows import router as workflows_router
from backend.app.routers.integrations import router as integrations_router
from backend.app.routers.automations import router as automations_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.webhooks import router as webhooks_router
from backend.app.middleware import security_middleware
from backend.app.routers.provider_events import router as provider_events_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.4.0",
    description="A secure, extensible automation hub.")
app.middleware("http")(security_middleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Automation-Signature"])

@app.on_event("startup")
def create_tables():
    if settings.app_env.lower() == "production":
        if len(settings.jwt_secret) < 32 or settings.jwt_secret.startswith("CHANGE-ME"):
            raise RuntimeError("Production requires a unique JWT_SECRET of at least 32 characters.")
        if not settings.oauth_encryption_key:
            raise RuntimeError("Production requires OAUTH_ENCRYPTION_KEY.")
        if settings.database_url.startswith("sqlite"):
            raise RuntimeError("SQLite is for local development; configure PostgreSQL in production.")
        if "*" in settings.allowed_origins:
            raise RuntimeError("Wildcard CORS origins are forbidden in production.")
        if not settings.allowed_origins or any(not origin.startswith("https://") for origin in settings.allowed_origins):
            raise RuntimeError("Production CORS origins must be explicit HTTPS origins.")
        if not settings.public_base_url.startswith("https://"):
            raise RuntimeError("Production requires PUBLIC_BASE_URL to be an HTTPS origin.")
        try:
            Fernet(settings.oauth_encryption_key.encode())
        except Exception as exc:
            raise RuntimeError("OAUTH_ENCRYPTION_KEY must be a valid Fernet key.") from exc
    Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(workflows_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(automations_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(provider_events_router, prefix="/api")

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "docs": "/docs",
            "worker": "separate-process: python -m backend.app.worker"}
