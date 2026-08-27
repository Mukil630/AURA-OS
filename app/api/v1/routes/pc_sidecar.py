"""Windows PC Hardware Telemetry REST Endpoints."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.connectors.pc_sidecar.collector import WindowsTelemetryCollector
from app.connectors.pc_sidecar.contracts import SystemHealthSummaryContract
from app.connectors.policy import default_policy_engine
from app.security.auth import AuthenticatedUser, get_current_user


router = APIRouter(prefix="/pc", tags=["Windows PC Telemetry Sidecar"])
_collector = WindowsTelemetryCollector(is_mock=True)


@router.get(
    "/health",
    response_model=SystemHealthSummaryContract,
    summary="Get Consolidated PC Health Telemetry",
    description="Returns read-only system telemetry (CPU, RAM, Disk, Network, Temperature). Strictly read-only sensor data.",
)
async def get_pc_health_summary(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SystemHealthSummaryContract:
    """Retrieve aggregate system metrics."""
    if not default_policy_engine.is_connector_enabled("connector_windows_sidecar"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Windows PC Sidecar connector is disabled by emergency kill-switch.",
        )

    summary = _collector.collect_health_summary()
    if not _collector.validate_metric_sanity(summary):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sensor validation failed: Telemetry values out of physical bounds.",
        )
    return summary


@router.get(
    "/metrics/{metric_type}",
    summary="Query Specific PC Hardware Metric",
    description="Retrieve component metrics ('cpu', 'memory', 'disk', 'network', 'temperature').",
)
async def get_pc_metric(
    metric_type: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve isolated component metric."""
    if not default_policy_engine.is_connector_enabled("connector_windows_sidecar"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Windows PC Sidecar connector is disabled by emergency kill-switch.",
        )

    m = metric_type.lower().strip()
    if m == "cpu":
        return _collector.collect_cpu().model_dump()
    elif m in ("memory", "ram"):
        return _collector.collect_memory().model_dump()
    elif m == "disk":
        return _collector.collect_disk().model_dump()
    elif m == "network":
        return _collector.collect_network().model_dump()
    elif m in ("temperature", "temp"):
        return _collector.collect_temperature().model_dump()
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown telemetry metric '{metric_type}'. Supported: cpu, memory, disk, network, temperature.",
        )
