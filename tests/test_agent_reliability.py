"""Test suite for multi-agent reliability fixes (test_agent_reliability.py).
Validates circuit breaker, health registry, intent validator, and failover.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.circuit_breaker import CircuitBreaker, BreakerState
from brain.agent_health_monitor import AgentHealthRegistry, health_registry
from brain.intent_validator import validate_tool_call, detect_hallucinated_result
from app.agents.swarm.base_swarm_agent import SwarmTaskMessage
from app.agents.swarm.swarm_orchestrator import SwarmOrchestrator


def test_circuit_breaker():
    print("=== Test: Circuit Breaker ===")
    cb = CircuitBreaker("test_agent", failure_threshold=2, timeout_seconds=0.5)

    assert cb.allow_call() is True, "Should allow call in CLOSED state"
    assert cb.state == BreakerState.CLOSED

    cb.record_failure(Exception("fail 1"))
    assert cb.state == BreakerState.CLOSED, "Should still be CLOSED after 1 failure"
    assert cb.allow_call() is True

    cb.record_failure(Exception("fail 2"))
    assert cb.state == BreakerState.OPEN, "Should be OPEN after 2 failures"
    assert cb.allow_call() is False, "Should block calls when OPEN"

    cb.record_success()
    assert cb.state == BreakerState.CLOSED, "Should reset to CLOSED on success"
    assert cb.allow_call() is True

    print("  PASSED\n")


def test_intent_validator():
    print("=== Test: Intent Validator ===")

    valid, err = validate_tool_call("read_file", {"file_path": "main.py"})
    assert valid is True, f"read_file with valid path should pass: {err}"

    valid, err = validate_tool_call("read_file", {"file_path": ""})
    assert valid is False, "read_file with empty path should fail"
    assert "empty" in err.lower()

    valid, err = validate_tool_call("read_file", {})
    assert valid is False, "read_file with missing param should fail"

    valid, err = validate_tool_call("run_command", {"command": "rm -rf /"})
    assert valid is False, "Dangerous command should be blocked"
    assert "dangerous" in err.lower()

    valid, err = validate_tool_call("nonexistent_tool", {"foo": "bar"})
    assert valid is False, "Unknown tool should fail"

    hallucinated, reason = detect_hallucinated_result("grep_search", "No matches found for query: test")
    assert hallucinated is True, "Known empty result should be detected as hallucinated"

    hallucinated, reason = detect_hallucinated_result("grep_search", "some_file.py:42: def hello():")
    assert hallucinated is False, "Real grep result should pass"

    print("  PASSED\n")


def test_antigravity_no_hallucination():
    print("=== Test: AntigravityAgent — No Fake Success ===")
    from app.agents.swarm.antigravity_agent import AntigravityAgent

    agent = AntigravityAgent()

    msg = SwarmTaskMessage(
        task_id="t1", sender="test", recipient="Antigravity",
        action="UNKNOWN_ACTION_TYPE", payload={"description": "do a thing"}
    )
    result = asyncio.run(agent.process_task(msg))
    assert result.status == "FAILED", f"Unknown action should fail, got: {result.status}"
    assert "not support" in result.error.lower() or "unsupported" in result.error.lower(), \
        f"Error should mention unsupported action, got: {result.error}"
    print("  PASSED — Unknown actions are rejected, not hallucinated as success\n")


def test_webscout_fallback_flagging():
    print("=== Test: WebScoutAgent — Fallback Flagging ===")
    from app.agents.swarm.web_scout_agent import WebScoutAgent

    agent = WebScoutAgent()

    msg = SwarmTaskMessage(
        task_id="t2", sender="test", recipient="WebScout",
        action="SCRAPE_JOBS", payload={"query": "Python Developer", "location": "Remote"}
    )
    result = asyncio.run(agent.process_task(msg))
    assert result.status == "COMPLETED", f"Should complete (with fallback): {result.status}"
    assert "source" in result.result, "Result should include 'source' field"
    assert result.result["source"] in ("fallback_mock", "live_jobspy"), \
        f"Source should be clearly labeled, got: {result.result.get('source')}"
    print(f"  PASSED — Result source clearly labeled: {result.result['source']}\n")


def test_orchestrator_failover():
    print("=== Test: SwarmOrchestrator — Circuit Breaker Failover ===")

    async def run():
        orchestrator = SwarmOrchestrator()

        # Dispatch a real task to Antigravity
        result = await orchestrator.dispatch(
            target_agent="Antigravity",
            action="VIEW_FILE",
            payload={"file_path": "brain/circuit_breaker.py", "end": 5}
        )
        assert result.status == "COMPLETED", f"Antigravity should succeed: {result.error or result.status}"
        assert result.result.get("verification") == "PASSED", \
            f"Should have verification PASSED: {result.result}"

        # Dispatch an unsupported action to Antigravity — should failover to backup
        result2 = await orchestrator.dispatch(
            target_agent="Antigravity",
            action="UNKNOWN_TOOL",
            payload={"description": "do something weird"}
        )
        assert result2.status == "FAILED", \
            f"Failover should also fail since backup can't do unknown action: {result2.status}"
        assert "not supported" in result2.error.lower() or "no agent" in result2.error.lower(), \
            f"Should have structured error: {result2.error}"

        print(f"  Backup agents configured: {orchestrator.backup_agent_map['Antigravity']}")
        print(f"  Status report available: {'agents' in orchestrator.get_status_report()}")

    asyncio.run(run())
    print("  PASSED — Failover works, errors are structured\n")


def test_orchestrator_health_report():
    print("=== Test: Orchestrator Health Report ===")
    orch = SwarmOrchestrator()
    report = orch.get_status_report()
    assert "agents" in report, "Report should contain agent health"
    assert "unhealthy_agents" in report, "Report should list unhealthy agents"
    assert len(report["agents"]) == 7, f"Should have 7 agents registered, got {len(report['agents'])}"
    print(f"  Agents tracked: {list(report['agents'].keys())}")
    print("  PASSED\n")


if __name__ == "__main__":
    test_circuit_breaker()
    test_intent_validator()
    test_antigravity_no_hallucination()
    test_webscout_fallback_flagging()
    test_orchestrator_failover()
    test_orchestrator_health_report()
    print("=== ALL TESTS PASSED ===")
