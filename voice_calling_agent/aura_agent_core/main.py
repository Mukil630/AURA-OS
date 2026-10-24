import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aura_agent_core.database import init_database
from aura_agent_core.api_router import router as core_router
from aura_agent_core.scheduler_daemon import AuraSchedulerDaemon

scheduler = AuraSchedulerDaemon()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Initialize Turso Cloud Tables
    print("[*] Initializing Turso Cloud Database Schema...")
    await init_database()
    print("[SUCCESS] Turso Database is ready!")

    # 2. Startup: Launch 24/7 Background Scheduler Daemon
    daemon_task = asyncio.create_task(scheduler.start())
    print("[SUCCESS] Scheduler Daemon started in background!")

    yield

    # 3. Shutdown: Clean termination
    scheduler.stop()
    daemon_task.cancel()
    print("[*] AURA-OS Server shutdown complete.")


app = FastAPI(
    title="AURA-OS Autonomous Core Engine",
    description="Multi-Agent Universal Memory, Scheduler & Cloud Turso Backend",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for Mobile Hub & Web Dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Core Router
app.include_router(core_router)


@app.get("/")
def health_check():
    return {
        "status": "online",
        "system": "AURA-OS Core Engine",
        "cloud_database": "Turso LibSQL Cloud",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("aura_agent_core.main:app", host="0.0.0.0", port=8000, reload=True)
