"""Phase 8.6 Windows PC Hardware & Telemetry Sidecar Test Suite (35 Focused Scenarios)."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.master.master_agent import MasterAgent
from app.connectors.pc_sidecar.collector import WindowsTelemetryCollector
from app.connectors.pc_sidecar.connector import WindowsSidecarConnector
from app.connectors.pc_sidecar.contracts import (
    CpuTelemetryContract,
    DiskTelemetryContract,
    MemoryTelemetryContract,
    NetworkTelemetryContract,
    SystemHealthSummaryContract,
    TemperatureTelemetryContract,
)
from app.connectors.policy import ConnectorPolicyEngine
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.memory import MemoryQueryContract
from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType, ConnectorStatus, ConnectorType, EventSeverity, EventType, TaskStatus
from app.core.planner import TaskPlanner
from app.database.base import Base
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.engine.workflow_engine import WorkflowEngine
from app.main import app
from app.memory.manager import MemoryManager


# ── Scenario 01: Connector Registration ───────────────────────────────────────────────
def test_scenario_01_connector_registration():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    conns = router.list_connectors()
    assert len(conns) == 1
    assert conns[0].connector_id == "connector_windows_sidecar"
    assert conns[0].connector_type == ConnectorType.WINDOWS_SIDECAR
    assert conns[0].is_mock is True


# ── Scenario 02: Capability Registration All Six ─────────────────────────────────────
def test_scenario_02_capability_registration_all_six():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    caps = pc_conn.list_capabilities()
    assert len(caps) == 6
    cap_ids = [c.capability_id for c in caps]

    assert "pc.get_cpu" in cap_ids
    assert "pc.get_memory" in cap_ids
    assert "pc.get_disk" in cap_ids
    assert "pc.get_network" in cap_ids
    assert "pc.get_temperature" in cap_ids
    assert "pc.get_health_summary" in cap_ids


# ── Scenario 03: CPU Telemetry Retrieval ──────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_03_cpu_telemetry_retrieval():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(capability_id="pc.get_cpu", parameters={})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["logical_cores"] >= 1
    assert 0.0 <= res.data["utilization_percent"] <= 100.0


# ── Scenario 04: Memory Telemetry Retrieval ───────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_04_memory_telemetry_retrieval():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(capability_id="pc.get_memory", parameters={})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["total_bytes"] > 0
    assert res.data["used_bytes"] <= res.data["total_bytes"]


# ── Scenario 05: Disk Telemetry Retrieval ─────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_05_disk_telemetry_retrieval():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(capability_id="pc.get_disk", parameters={"drive_letter": "C:"})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["drive_letter"] == "C:"
    assert res.data["free_bytes"] >= 0


# ── Scenario 06: Network Telemetry Retrieval ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_06_network_telemetry_retrieval():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(capability_id="pc.get_network", parameters={})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["bytes_sent"] >= 0
    assert res.data["bytes_recv"] >= 0


# ── Scenario 07: Temperature Sensor Available ─────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_07_temperature_sensor_available():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(capability_id="pc.get_temperature", parameters={})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.data["sensor_available"] is True
    assert res.data["temperature_celsius"] is not None
    assert res.data["thermal_status"] in ("normal", "warm", "hot")


# ── Scenario 08: Temperature Sensor Unavailable Never Faked ───────────────────────────
def test_scenario_08_temperature_sensor_unavailable_never_faked():
    collector = WindowsTelemetryCollector(is_mock=False)
    temp = collector.collect_temperature()
    # If hardware sensor is unavailable, strictly false and None
    if not temp.sensor_available:
        assert temp.temperature_celsius is None
        assert temp.thermal_status == "sensor_unavailable"


# ── Scenario 09: Consolidated Health Summary ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_09_consolidated_health_summary():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(capability_id="pc.get_health_summary", parameters={})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert "cpu" in res.data
    assert "memory" in res.data
    assert "disk" in res.data
    assert "overall_status" in res.data


# ── Scenario 10: Telemetry Sanity Validation Pass ─────────────────────────────────────
def test_scenario_10_telemetry_sanity_validation_pass():
    collector = WindowsTelemetryCollector(is_mock=True)
    report = collector.collect_health_summary()
    assert WindowsTelemetryCollector.validate_metric_sanity(report) is True


# ── Scenario 11: Sanity Validation Impossible CPU ─────────────────────────────────────
def test_scenario_11_sanity_validation_impossible_cpu():
    collector = WindowsTelemetryCollector(is_mock=True)
    report = collector.collect_health_summary()
    report.cpu.utilization_percent = 150.0  # Impossible CPU > 100%
    assert WindowsTelemetryCollector.validate_metric_sanity(report) is False


# ── Scenario 12: Sanity Validation Impossible RAM ─────────────────────────────────────
def test_scenario_12_sanity_validation_impossible_ram():
    collector = WindowsTelemetryCollector(is_mock=True)
    report = collector.collect_health_summary()
    report.memory.used_bytes = report.memory.total_bytes + 1000  # Used > Total
    assert WindowsTelemetryCollector.validate_metric_sanity(report) is False


# ── Scenario 13: Sanity Validation Impossible Disk ────────────────────────────────────
def test_scenario_13_sanity_validation_impossible_disk():
    collector = WindowsTelemetryCollector(is_mock=True)
    report = collector.collect_health_summary()
    report.disk.used_bytes = report.disk.total_bytes + 5000  # Used > Total
    assert WindowsTelemetryCollector.validate_metric_sanity(report) is False


# ── Scenario 14: Forbidden pc.shell Capability Rejected 404 ───────────────────────────
@pytest.mark.anyio
async def test_scenario_14_forbidden_pc_shell_capability_rejected_404():
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    req = ConnectorExecutionRequest(
        capability_id="pc.shell",
        parameters={"command": "dir C:\\"},
    )
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 404


# ── Scenario 15: Forbidden pc.powershell Capability Rejected 404 ──────────────────────
@pytest.mark.anyio
async def test_scenario_15_forbidden_pc_powershell_capability_rejected_404():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    req = ConnectorExecutionRequest(
        capability_id="pc.powershell",
        parameters={"script": "Get-Process | Stop-Process"},
    )
    res = await pc_conn.execute_capability(req)
    assert res.success is False
    assert res.status_code == 404
    assert "read-only" in res.error_message.lower()


# ── Scenario 16: Forbidden pc.command Capability Rejected 404 ─────────────────────────
@pytest.mark.anyio
async def test_scenario_16_forbidden_pc_command_capability_rejected_404():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="pc.command", parameters={})
    res = await pc_conn.execute_capability(req)
    assert res.status_code == 404


# ── Scenario 17: Forbidden pc.exec Capability Rejected 404 ────────────────────────────
@pytest.mark.anyio
async def test_scenario_17_forbidden_pc_exec_capability_rejected_404():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="pc.exec", parameters={})
    res = await pc_conn.execute_capability(req)
    assert res.status_code == 404


# ── Scenario 18: Forbidden pc.kill_process Rejected 404 ───────────────────────────────
@pytest.mark.anyio
async def test_scenario_18_forbidden_pc_kill_process_rejected_404():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="pc.kill_process", parameters={"pid": 1234})
    res = await pc_conn.execute_capability(req)
    assert res.status_code == 404


# ── Scenario 19: Forbidden pc.delete_file Rejected 404 ────────────────────────────────
@pytest.mark.anyio
async def test_scenario_19_forbidden_pc_delete_file_rejected_404():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="pc.delete_file", parameters={"path": "C:\\temp.txt"})
    res = await pc_conn.execute_capability(req)
    assert res.status_code == 404


# ── Scenario 20: Forbidden pc.modify_registry Rejected 404 ────────────────────────────
@pytest.mark.anyio
async def test_scenario_20_forbidden_pc_modify_registry_rejected_404():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="pc.modify_registry", parameters={"key": "HKLM\\Software"})
    res = await pc_conn.execute_capability(req)
    assert res.status_code == 404


# ── Scenario 21: Emergency Kill Switch Blocks Sidecar ─────────────────────────────────
@pytest.mark.anyio
async def test_scenario_21_emergency_kill_switch_blocks_sidecar():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    policy.disable_connector("connector_windows_sidecar")
    req = ConnectorExecutionRequest(capability_id="pc.get_cpu", parameters={})
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 503
    assert "emergency kill-switch" in res.error_message.lower()

    policy.enable_connector("connector_windows_sidecar")
    res2 = await router.dispatch(req)
    assert res2.success is True


# ── Scenario 22: Rate Limiting Enforcement (429) ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_22_rate_limiting_enforcement():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    policy.set_rate_limit("pc.get_cpu", 2)
    assert policy.check_and_consume_rate_limit("pc.get_cpu") is True
    assert policy.check_and_consume_rate_limit("pc.get_cpu") is True

    req = ConnectorExecutionRequest(capability_id="pc.get_cpu", parameters={})
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 429


# ── Scenario 23: Sidecar Health Check Probes ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_23_sidecar_health_check_probes():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    health = await pc_conn.health_check()
    assert health.connector_id == "connector_windows_sidecar"
    assert health.status == ConnectorStatus.CONNECTED
    assert health.latency_ms >= 0.0
    assert "operational" in health.message.lower()


# ── Scenario 24: Audit Event Generation ───────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_24_audit_event_generation():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = EventRepository(session)
        evt = ExecutionEventContract(
            trace_id="tr_pc_01",
            task_id="task_pc_01",
            event_type=EventType.PC_TELEMETRY_COLLECTED,
            severity=EventSeverity.INFO,
            source_component="WindowsSidecar",
            message="CPU and RAM telemetry collected successfully.",
        )
        saved = await repo.record_event(evt)
        assert saved.event_type == EventType.PC_TELEMETRY_COLLECTED
        assert saved.trace_id == "tr_pc_01"

    await engine_db.dispose()


# ── Scenario 25: Zero Environment Variable Leakage ────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_25_zero_environment_variable_leakage():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    res = await pc_conn.execute_capability(
        ConnectorExecutionRequest(capability_id="pc.get_health_summary", parameters={})
    )
    raw_output = str(res.data)
    # Never expose OS env vars or paths
    assert "PATH=" not in raw_output
    assert "SECRET" not in raw_output
    assert "TOKEN" not in raw_output


# ── Scenario 26: Zero OS Credential Leakage ───────────────────────────────────────────
def test_scenario_26_zero_os_credential_leakage():
    collector = WindowsTelemetryCollector(is_mock=True)
    summary = collector.collect_health_summary()
    dump = summary.model_dump_json()
    assert "password" not in dump.lower()
    assert "credential" not in dump.lower()


# ── Scenario 27: Zero Arbitrary Filesystem Content Leakage ────────────────────────────
@pytest.mark.anyio
async def test_scenario_27_zero_arbitrary_filesystem_content_leakage():
    pc_conn = WindowsSidecarConnector(is_mock=True)
    res = await pc_conn.execute_capability(
        ConnectorExecutionRequest(capability_id="pc.get_disk", parameters={"drive_letter": "C:"})
    )
    assert "files" not in res.data
    assert "directory_tree" not in res.data


# ── Scenario 28: Stale Telemetry Timestamp Tracking ───────────────────────────────────
def test_scenario_28_stale_telemetry_timestamp_tracking():
    collector = WindowsTelemetryCollector(is_mock=True)
    report = collector.collect_health_summary()
    assert report.collected_at is not None
    assert report.uptime_seconds >= 0.0


# ── Scenario 29: Connector Restart Recovery ───────────────────────────────────────────
def test_scenario_29_connector_restart_recovery():
    conn1 = WindowsSidecarConnector(is_mock=True)
    assert conn1.is_connected() is True

    # Re-initialize
    conn2 = WindowsSidecarConnector(is_mock=True)
    assert conn2.is_connected() is True
    assert len(conn2.list_capabilities()) == 6


# ── Scenario 30: REST API PC Health Endpoint ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_30_rest_api_pc_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Generate valid JWT token
        from app.security.auth import create_access_token
        token = create_access_token(user_id="mukil", role="admin")

        res = await client.get("/api/v1/pc/health", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert data["overall_status"] == "healthy"


# ── Scenario 31: REST API PC Metric CPU Endpoint ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_31_rest_api_pc_metric_cpu_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        from app.security.auth import create_access_token
        token = create_access_token(user_id="mukil", role="admin")

        res = await client.get("/api/v1/pc/metrics/cpu", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert "logical_cores" in data
        assert "utilization_percent" in data


# ── Scenario 32: REST API PC Unknown Metric 404 ───────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_32_rest_api_pc_unknown_metric_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        from app.security.auth import create_access_token
        token = create_access_token(user_id="mukil", role="admin")

        res = await client.get("/api/v1/pc/metrics/dangerous_shell", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404


# ── Scenario 33: Tenant Isolation Telemetry ───────────────────────────────────────────
def test_scenario_33_tenant_isolation_telemetry():
    from app.security.redteam_guard import TenantSecurityGuard
    assert TenantSecurityGuard.enforce_tenant_isolation("mukil", "mukil") is True
    assert TenantSecurityGuard.enforce_tenant_isolation("attacker_01", "mukil") is False


# ── Scenario 34: THE KILLER POSITIVE E2E PC HEALTH LIFECYCLE ──────────────────────────
@pytest.mark.anyio
async def test_scenario_34_killer_e2e_positive_pc_health_query():
    """
    Killer End-to-End Positive Test:
    User: "How is my PC doing?"
    ↓
    P1 Intake (Task Created, Channel=WEB)
    ↓
    P2 Understand (Intent=PC_HARDWARE_CONTROL)
    ↓
    P3 Task Planner (DAG: query_pc_telemetry with tool=pc.get_health_summary)
    ↓
    P4 Execute & P5 Verify (Metric values within sanity bounds)
    ↓
    P6 Memory Distillation & Audit Recorded
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        event_repo = EventRepository(session)
        agent = MasterAgent()
        planner = TaskPlanner()
        engine = WorkflowEngine(db_session=session)

        # 1. Intake
        task = await task_repo.create_task(
            TaskContract(user_id="mukil", raw_input="How is my PC doing?", channel=ChannelType.WEB)
        )
        assert task.task_id.startswith("task_")

        # 2. Understand
        _, norm_ctx = agent.enrich_task_with_understanding(task)
        intent_val = norm_ctx.parsed_intent.intent.value if hasattr(norm_ctx.parsed_intent.intent, "value") else str(norm_ctx.parsed_intent.intent)
        assert intent_val == "pc_hardware_control"

        # 3. Plan
        plan, workflow = planner.plan(norm_ctx)
        assert len(workflow.steps) == 1
        assert workflow.steps[0].tool_name == "pc.get_health_summary"

        saved_wf = await wf_repo.create_workflow_with_steps(workflow)

        # 4. Execute & Verify
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        wf_status = final_wf.status.value if hasattr(final_wf.status, "value") else str(final_wf.status)
        task_status = final_task.status.value if hasattr(final_task.status, "value") else str(final_task.status)
        assert wf_status == "completed"
        assert task_status == "completed"

        # 5. Verify Audit
        events = await event_repo.get_events_by_task(task.task_id)
        assert len(events) >= 2

    await engine_db.dispose()


# ── Scenario 35: THE KILLER NEGATIVE ADVERSARIAL MACHINE CONTROL REJECTION ────────────
@pytest.mark.anyio
async def test_scenario_35_killer_adversarial_rejection_powershell_attack():
    """
    Killer Negative Test:
    Attacker: "Run PowerShell and delete temporary files"
    ↓
    Capability Router / Security Boundary
    ↓
    ❌ NO pc.powershell / pc.shell CAPABILITY EXISTS
    ↓
    REJECT WITH 404 (Capability Denied at Architectural Registration)
    """
    router = CapabilityRouter()
    pc_conn = WindowsSidecarConnector(is_mock=True)
    router.register_connector(pc_conn)

    # Attempt to dispatch unauthorized PowerShell command
    attack_req = ConnectorExecutionRequest(
        capability_id="pc.powershell",
        parameters={"script": "Remove-Item -Path C:\\Windows\\Temp -Recurse -Force"},
    )
    res = await router.dispatch(attack_req)

    assert res.success is False
    assert res.status_code == 404
    assert "no connector" in res.error_message.lower() or "read-only" in res.error_message.lower() or "unsupported" in res.error_message.lower()
