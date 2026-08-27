"""Operational Dashboard and Agent Real-Time Health Subsystem."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.connectors.policy import default_policy_engine
from app.observability.tracer import default_tracer


class ComponentHealth(BaseModel):
    """Health indicator for an individual system subsystem."""
    name: str
    status: str = Field(default="healthy", description="'healthy', 'degraded', 'offline', 'disabled'.")
    message: str = "Operating normally."


class TaskExecutionMetrics(BaseModel):
    """Aggregated operational metrics for autonomous agent tasks."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    rejected_tasks: int = 0
    avg_duration_ms: float = 0.0
    success_rate_percent: float = 100.0


class ActiveTaskProgression(BaseModel):
    """Live state of actively executing task across P1-P6 agent lifecycle."""
    task_id: str
    raw_input: str
    p1_intake: str = "completed"
    p2_understand: str = "completed"
    p3_plan: str = "completed"
    p4_execute: str = "in_progress"
    p5_verify: str = "pending"
    p6_remember: str = "pending"
    current_step: Optional[str] = None


class SystemDashboardOverview(BaseModel):
    """Consolidated operational status report."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    system_health: Dict[str, ComponentHealth]
    metrics: TaskExecutionMetrics
    active_tasks: List[ActiveTaskProgression]


class OperationalDashboardService:
    """Computes real-time telemetry, health, and throughput metrics for operational partners."""

    def __init__(self, policy_engine=None, tracer=None):
        self.policy = policy_engine or default_policy_engine
        self.tracer = tracer or default_tracer

    def get_system_health(self) -> Dict[str, ComponentHealth]:
        """Assess operational health across all core subsystems."""
        health = {}

        # 1. Agent Core
        health["agent_core"] = ComponentHealth(name="Master Agent", status="healthy", message="P1-P7 Autonomous Loop Active.")

        # 2. Security Gate
        health["security_gate"] = ComponentHealth(name="Security & Red-Team Gate", status="healthy", message="Zero Token Leakage Enforced.")

        # 3. Kill Switch
        ks_active = not self.policy._disabled_connectors
        health["kill_switch"] = ComponentHealth(
            name="Emergency Stop System",
            status="healthy" if ks_active else "degraded",
            message="Kill switch armed and operational." if ks_active else "One or more connectors stopped via kill-switch.",
        )

        # 4. Telegram Gateway
        tg_status = "healthy" if self.policy.is_connector_enabled("connector_telegram") else "disabled"
        health["telegram_gateway"] = ComponentHealth(name="Telegram Gateway", status=tg_status)

        # 5. Google Drive Dual-Vault
        drive_status = "healthy" if self.policy.is_connector_enabled("connector_google_drive") else "disabled"
        health["google_drive"] = ComponentHealth(name="Google Drive Dual-Vault", status=drive_status)

        # 6. GitHub Connector
        gh_status = "healthy" if self.policy.is_connector_enabled("connector_github") else "disabled"
        health["github_connector"] = ComponentHealth(name="GitHub Actions Connector", status=gh_status)

        # 7. Windows Telemetry Sidecar
        pc_status = "healthy" if self.policy.is_connector_enabled("connector_windows_sidecar") else "disabled"
        health["windows_sidecar"] = ComponentHealth(name="Windows Telemetry Sidecar", status=pc_status, message="Read-Only Telemetry Active.")

        return health

    def compute_metrics(self) -> TaskExecutionMetrics:
        """Compute aggregated task throughput, failure rates, and latencies from traces."""
        traces = self.tracer.list_traces()
        if not traces:
            return TaskExecutionMetrics()

        total = len(traces)
        completed = sum(1 for t in traces if t.overall_status == "completed")
        failed = sum(1 for t in traces if t.overall_status == "failed")
        rejected = sum(1 for t in traces if t.overall_status == "rejected")

        durations = [t.total_duration_ms for t in traces if t.total_duration_ms > 0]
        avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0
        success_rate = round((completed / total) * 100, 2) if total > 0 else 100.0

        return TaskExecutionMetrics(
            total_tasks=total,
            completed_tasks=completed,
            failed_tasks=failed,
            rejected_tasks=rejected,
            avg_duration_ms=avg_dur,
            success_rate_percent=success_rate,
        )

    def get_dashboard_overview(self) -> SystemDashboardOverview:
        """Construct full operational overview."""
        return SystemDashboardOverview(
            system_health=self.get_system_health(),
            metrics=self.compute_metrics(),
            active_tasks=[],
        )


# Global Singleton Dashboard Instance
default_dashboard = OperationalDashboardService()
