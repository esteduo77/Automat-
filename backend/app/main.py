import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import get_settings
from backend.app.database import Base, engine
from backend.app import models
from backend.app.routers.health import router as health_router
from backend.app.routers.workflows import router as workflows_router
from backend.app.routers.integrations import router as integrations_router
from backend.app.routers.automations import router as automations_router
from backend.app.services.automation_worker import worker_loop

settings = get_settings()

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    stop = asyncio.Event()
    worker = asyncio.create_task(worker_loop(stop))
    try:
        yield
    finally:
        stop.set()
        await worker

app = FastAPI(title=settings.app_name, version="0.3.0",
    description="A secure, extensible automation hub.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"])
app.include_router(health_router, prefix="/api")
app.include_router(workflows_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(automations_router, prefix="/api")

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}
