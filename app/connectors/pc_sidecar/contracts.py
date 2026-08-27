"""Data contracts for Windows PC Hardware & System Telemetry (Read-Only Sensor Models)."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from app.core.contracts.base import VersionedContractBase


class CpuTelemetryContract(BaseModel):
    """CPU load and processor metrics."""
    logical_cores: int = Field(..., ge=1, description="Number of logical processor threads.")
    physical_cores: int = Field(..., ge=1, description="Number of physical CPU cores.")
    utilization_percent: float = Field(..., ge=0.0, le=100.0, description="Current CPU utilization (0.0 to 100.0%).")
    load_average: List[float] = Field(default_factory=list, description="1m, 5m, 15m load average estimates.")


class MemoryTelemetryContract(BaseModel):
    """System RAM allocation and usage metrics."""
    total_bytes: int = Field(..., gt=0, description="Total physical RAM in bytes.")
    used_bytes: int = Field(..., ge=0, description="RAM currently in use.")
    available_bytes: int = Field(..., ge=0, description="RAM available for allocation.")
    utilization_percent: float = Field(..., ge=0.0, le=100.0, description="RAM utilization percentage.")


class DiskTelemetryContract(BaseModel):
    """Primary system storage drive telemetry."""
    drive_letter: str = Field(default="C:", description="Target storage partition.")
    total_bytes: int = Field(..., gt=0, description="Total drive capacity in bytes.")
    used_bytes: int = Field(..., ge=0, description="Storage consumed.")
    free_bytes: int = Field(..., ge=0, description="Storage remaining free.")
    utilization_percent: float = Field(..., ge=0.0, le=100.0, description="Disk utilization percentage.")


class NetworkTelemetryContract(BaseModel):
    """Network I/O throughput telemetry."""
    bytes_sent: int = Field(..., ge=0, description="Total bytes transmitted.")
    bytes_recv: int = Field(..., ge=0, description="Total bytes received.")
    packets_sent: int = Field(default=0, ge=0, description="Packets transmitted.")
    packets_recv: int = Field(default=0, ge=0, description="Packets received.")
    interface_count: int = Field(default=1, ge=1, description="Number of active network interfaces.")


class TemperatureTelemetryContract(BaseModel):
    """Hardware thermal sensor telemetry."""
    sensor_available: bool = Field(default=False, description="True only if hardware thermal sensors are detected.")
    temperature_celsius: Optional[float] = Field(default=None, description="Current package temperature in °C.")
    thermal_status: str = Field(default="normal", description="'normal', 'warm', 'hot', or 'sensor_unavailable'.")


class SystemHealthSummaryContract(VersionedContractBase):
    """Comprehensive read-only system telemetry report."""
    telemetry_id: str = Field(default_factory=lambda: f"tel_{uuid4().hex[:10]}", description="Unique telemetry probe ID.")
    hostname: str = Field(default="MUKIL-WORKSTATION", description="Machine hostname.")
    os_platform: str = Field(default="Windows 11 Pro 64-bit", description="Operating system platform.")
    uptime_seconds: float = Field(..., ge=0.0, description="System uptime in seconds.")
    cpu: CpuTelemetryContract = Field(..., description="CPU telemetry.")
    memory: MemoryTelemetryContract = Field(..., description="Memory telemetry.")
    disk: DiskTelemetryContract = Field(..., description="Storage telemetry.")
    network: NetworkTelemetryContract = Field(..., description="Network throughput telemetry.")
    temperature: TemperatureTelemetryContract = Field(..., description="Thermal sensor telemetry.")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of probe collection."
    )
    collection_latency_ms: float = Field(default=0.0, ge=0.0, description="Collector execution time in milliseconds.")
    overall_status: str = Field(default="healthy", description="Overall assessment ('healthy', 'degraded', 'warning').")
