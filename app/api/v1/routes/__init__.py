"""Re-export API v1 routes."""
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.tasks import router as tasks_router
from app.api.v1.routes.auth import router as auth_router

__all__ = ["health_router", "tasks_router", "auth_router"]
