"""Unit tests for ExecutionEvent and Audit Contracts."""
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.enums import EventSeverity, EventType


def test_execution_event_contract():
    evt = ExecutionEventContract(
        trace_id="tr_999888777",
        task_id="task_123",
        event_type=EventType.STEP_COMPLETED,
        severity=EventSeverity.INFO,
        source_component="WorkflowEngine",
        message="Step 0 completed successfully in 120ms.",
        payload={"step_index": 0, "duration_ms": 120},
    )
    assert evt.event_id.startswith("evt_")
    assert evt.trace_id == "tr_999888777"
    assert evt.event_type == EventType.STEP_COMPLETED
    assert evt.source_component == "WorkflowEngine"
    assert evt.payload["duration_ms"] == 120
