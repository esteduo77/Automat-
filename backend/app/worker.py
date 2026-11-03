"""Standalone worker entry point: python -m backend.app.worker."""
import asyncio
import logging
from backend.app.database import Base, engine
from backend.app import models
from backend.app.services.automation_worker import worker_loop

logging.basicConfig(level=logging.INFO)

async def main():
    Base.metadata.create_all(bind=engine)
    stop = asyncio.Event()
    try:
        await worker_loop(stop)
    except KeyboardInterrupt:
        stop.set()

if __name__ == "__main__":
    asyncio.run(main())
