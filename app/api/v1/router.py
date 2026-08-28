"""Aggregate API v1 Router."""
from fastapi import APIRouter
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.master import router as master_router
from app.api.v1.routes.planner import router as planner_router
from app.api.v1.routes.tasks import router as tasks_router
from app.api.v1.routes.workflow import router as workflow_router
from app.api.v1.routes.verification import router as verification_router
from app.api.v1.routes.memory import router as memory_router
from app.api.v1.routes.connectors import router as connectors_router
from app.api.v1.routes.pc_sidecar import router as pc_sidecar_router
from app.api.v1.routes.telegram_webhook import router as telegram_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.approvals import router as approvals_router
from app.api.v1.routes.bridge import router as bridge_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(master_router)
api_v1_router.include_router(planner_router)
api_v1_router.include_router(workflow_router)
api_v1_router.include_router(verification_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(connectors_router)
api_v1_router.include_router(telegram_router)
api_v1_router.include_router(pc_sidecar_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(approvals_router)
api_v1_router.include_router(bridge_router)

