"""Windows PC Hardware & Telemetry Sidecar Connector (Strictly Read-Only)."""
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.connectors.pc_sidecar.collector import WindowsTelemetryCollector
from app.connectors.pc_sidecar.contracts import (
    CpuTelemetryContract,
    DiskTelemetryContract,
    MemoryTelemetryContract,
    NetworkTelemetryContract,
    SystemHealthSummaryContract,
    TemperatureTelemetryContract,
)
from app.core.contracts.connector import (
    CapabilityContract,
    ConnectorContract,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorHealthContract,
)
from app.core.enums import AuthType, ConnectorStatus, ConnectorType, RiskTier
from app.core.interfaces.connector import IConnector


# ── Explicit List of Permitted Telemetry Capabilities (Read-Only) ─────────────
READONLY_CAPABILITIES: Set[str] = {
    "pc.get_cpu",
    "pc.get_memory",
    "pc.get_disk",
    "pc.get_network",
    "pc.get_temperature",
    "pc.get_health_summary",
}

# ── Explicitly Forbidden Machine-Control Action Capabilities ──────────────────
FORBIDDEN_CONTROL_CAPABILITIES = {
    "pc.shell",
    "pc.powershell",
    "pc.command",
    "pc.exec",
    "pc.run",
    "pc.execute",
    "pc.kill_process",
    "pc.delete_file",
    "pc.modify_registry",
}


class WindowsSidecarConnector(IConnector):
    """
    Windows PC Hardware & Sensor Telemetry Connector.
    Strictly observes hardware utilization (CPU, RAM, Disk, Network, Temperature).
    NON-NEGOTIABLE SECURITY GUARANTEE: Does NOT support command execution, shell spawning,
    or OS mutations. All control capabilities are denied at the registration boundary.
    """

    def __init__(self, is_mock: Optional[bool] = None):
        self._connector_id = "connector_windows_sidecar"
        self._connector_type = ConnectorType.WINDOWS_SIDECAR
        env_mode = os.getenv("ENVIRONMENT", "mock").lower()
        self._is_mock = is_mock if is_mock is not None else (env_mode in ("mock", "test"))
        self._connected = True
        self._collector = WindowsTelemetryCollector(is_mock=self._is_mock)

        # 6 Strictly Read-Only Capabilities
        self._capabilities: List[CapabilityContract] = [
            CapabilityContract(
                capability_id="pc.get_cpu",
                connector_id=self._connector_id,
                name="Get CPU Telemetry",
                description="Query logical/physical core counts, utilization percent, and load statistics.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["telemetry:read"],
                timeout_seconds=10,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="pc.get_memory",
                connector_id=self._connector_id,
                name="Get Memory Telemetry",
                description="Query physical RAM capacity, active usage, and allocation metrics.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["telemetry:read"],
                timeout_seconds=10,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="pc.get_disk",
                connector_id=self._connector_id,
                name="Get Disk Telemetry",
                description="Query primary drive capacity, consumed bytes, and remaining free space.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["telemetry:read"],
                timeout_seconds=10,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="pc.get_network",
                connector_id=self._connector_id,
                name="Get Network Telemetry",
                description="Query network interface count, total bytes transmitted, and packet counts.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["telemetry:read"],
                timeout_seconds=10,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="pc.get_temperature",
                connector_id=self._connector_id,
                name="Get Temperature Telemetry",
                description="Query thermal sensors. Returns sensor_available=false if unavailable.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["telemetry:read"],
                timeout_seconds=10,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="pc.get_health_summary",
                connector_id=self._connector_id,
                name="Get PC Health Summary",
                description="Consolidated snapshot of CPU, RAM, Disk, Network, and thermal sensors.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["telemetry:read"],
                timeout_seconds=15,
                rate_limit_per_minute=30,
            ),
        ]

    @property
    def connector_id(self) -> str:
        return self._connector_id

    @property
    def connector_type(self) -> ConnectorType:
        return self._connector_type

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_contract(self) -> ConnectorContract:
        return ConnectorContract(
            connector_id=self.connector_id,
            name="Windows PC Hardware & Telemetry Sidecar",
            connector_type=self.connector_type,
            auth_type=AuthType.NONE,
            status=ConnectorStatus.CONNECTED if self._connected else ConnectorStatus.DISCONNECTED,
            base_url="local://windows_sidecar",
            supported_capabilities=[c.capability_id for c in self._capabilities],
            required_scopes=["telemetry:read"],
            health_check_endpoint="local://windows_sidecar/health",
            last_health_check=datetime.now(timezone.utc),
            is_mcp=False,
            is_mock=self._is_mock,
        )

    def list_capabilities(self) -> List[CapabilityContract]:
        return list(self._capabilities)

    async def health_check(self) -> ConnectorHealthContract:
        start = time.time()
        try:
            # Quick probe on CPU collector
            cpu = self._collector.collect_cpu()
            latency = round((time.time() - start) * 1000, 2)
            return ConnectorHealthContract(
                connector_id=self.connector_id,
                status=ConnectorStatus.CONNECTED,
                latency_ms=latency,
                message=f"Windows Telemetry Sidecar Operational (CPU: {cpu.utilization_percent}%).",
            )
        except Exception as e:
            return ConnectorHealthContract(
                connector_id=self.connector_id,
                status=ConnectorStatus.ERROR,
                latency_ms=round((time.time() - start) * 1000, 2),
                message=f"Collector probe error: {str(e)}",
            )

    async def execute_capability(
        self,
        request: ConnectorExecutionRequest,
        credentials: Optional[str] = None,
    ) -> ConnectorExecutionResult:
        """Execute read-only telemetry query with strict metric validation."""
        start = time.time()
        cap_id = request.capability_id
        params = request.parameters

        # ── Explicit Rejection of Machine Control / Shell Capabilities ────────────────
        if cap_id in FORBIDDEN_CONTROL_CAPABILITIES or "shell" in cap_id or "exec" in cap_id or "run" in cap_id:
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=False,
                status_code=404,
                error_message=f"Forbidden/Unsupported capability '{cap_id}': Windows Sidecar is strictly READ-ONLY telemetry.",
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # ── 1. CPU Telemetry ──────────────────────────────────────────────────────────
        if cap_id == "pc.get_cpu":
            cpu_data = self._collector.collect_cpu()
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=cpu_data.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # ── 2. Memory Telemetry ───────────────────────────────────────────────────────
        elif cap_id == "pc.get_memory":
            mem_data = self._collector.collect_memory()
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=mem_data.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # ── 3. Disk Telemetry ─────────────────────────────────────────────────────────
        elif cap_id == "pc.get_disk":
            drive = params.get("drive_letter", "C:")
            disk_data = self._collector.collect_disk(drive)
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=disk_data.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # ── 4. Network Telemetry ──────────────────────────────────────────────────────
        elif cap_id == "pc.get_network":
            net_data = self._collector.collect_network()
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=net_data.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # ── 5. Temperature Telemetry ──────────────────────────────────────────────────
        elif cap_id == "pc.get_temperature":
            temp_data = self._collector.collect_temperature()
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=temp_data.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # ── 6. Health Summary ─────────────────────────────────────────────────────────
        elif cap_id == "pc.get_health_summary":
            summary = self._collector.collect_health_summary()
            if not self._collector.validate_metric_sanity(summary):
                return ConnectorExecutionResult(
                    request_id=request.request_id,
                    capability_id=cap_id,
                    success=False,
                    status_code=422,
                    error_message="Sensor telemetry sanity check failed: Metric values exceed physical bounds.",
                    latency_ms=round((time.time() - start) * 1000, 2),
                )

            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=summary.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        return ConnectorExecutionResult(
            request_id=request.request_id,
            capability_id=cap_id,
            success=False,
            status_code=404,
            error_message=f"Unsupported capability '{cap_id}' in WindowsSidecarConnector.",
            latency_ms=round((time.time() - start) * 1000, 2),
        )
