"""
Diagnostic: test connectivity to every registered agent + intent translation.
Verifies that the cognitive router's track names are properly translated to
concrete agent actions, and that every agent responds correctly.
"""
import asyncio
import traceback
from app.agents.swarm.swarm_orchestrator import SwarmOrchestrator
from brain.agent_capability_registry import capability_registry


async def test_all_agents():
    orch = SwarmOrchestrator()
    print(f"Agents registered: {list(orch.agents.keys())}")
    print(f"Backup map: {orch.backup_agent_map}")
    print()

    # Test 1: Concrete action dispatch (action name matches what agent expects)
    print("=== Test 1: Concrete Action Dispatch ===")
    concrete_tests = {
        "Antigravity": ("VIEW_FILE", {"file_path": "brain/circuit_breaker.py", "end": 5}),
        "WebScout": ("SCRAPE_JOBS", {"query": "Python", "limit": 1}),
        "PlacementHunter": ("TAILOR_RESUME", {"company": "Zoho", "role": "AI Engineer"}),
        "SGCExecutive": ("CHECK_OVERDUE", {}),
        "MemoryVault": ("LIST_ALL_MESH_NODES", {}),
        "PCPilot": ("GET_BATTERY", {}),
        "ServerAgent": ("CHECK_SERVER_STATUS", {}),
    }

    all_passed = True
    for agent, (action, payload) in concrete_tests.items():
        try:
            result = await orch.dispatch(agent, action, payload, timeout=30)
            err_short = result.error[:80] if result.error else "none"
            status_icon = "OK" if result.status == "COMPLETED" else "FAIL"
            print(f"  [{status_icon}] {agent:20} | {action:25} | status={result.status} | error={err_short}")
            if result.status != "COMPLETED":
                all_passed = False
        except Exception as e:
            print(f"  [EXC] {agent:20} | {action:25} | EXCEPTION: {type(e).__name__}: {e}")
            traceback.print_exc()
            all_passed = False

    print()
    print("=== Test 2: Intent Translation (cognitive router track names) ===")
    # Test 2: High-level intent dispatch (track names from cognitive router)
    intent_tests = {
        "AUTONOMOUS_HEAVY_TASK (view_file)": (
            "AUTONOMOUS_HEAVY_TASK", "Antigravity",
            {"file_path": "brain/circuit_breaker.py", "end": 5}
        ),
        "DEVICE_PRESENTATION": (
            "DEVICE_PRESENTATION", "PCPilot",
            {"target": "https://kilo.ai"}
        ),
        "STATUS_OR_MEMORY_QUERY (server)": (
            "STATUS_OR_MEMORY_QUERY", "ServerAgent", {}
        ),
        "STATUS_OR_MEMORY_QUERY (sgc)": (
            "STATUS_OR_MEMORY_QUERY", "SGCExecutive", {}
        ),
        "STATUS_OR_MEMORY_QUERY (memory)": (
            "STATUS_OR_MEMORY_QUERY", "MemoryVault", {}
        ),
    }

    for label, (intent, agent, payload) in intent_tests.items():
        try:
            result = await orch.dispatch(agent, intent, payload, timeout=30)
            err_short = result.error[:80] if result.error else "none"
            status_icon = "OK" if result.status == "COMPLETED" else "FAI"
            print(f"  [{status_icon}] {label:35} | agent={agent:15} | status={result.status} | err={err_short}")
            if result.status != "COMPLETED":
                all_passed = False
        except Exception as e:
            print(f"  [EXC] {label:35} | EXCEPTION: {type(e).__name__}: {e}")
            traceback.print_exc()
            all_passed = False

    print()
    print("=== Test 3: Auto-Dispatch by Intent Alone (no agent specified) ===")
    auto_tests = [
        ("VIEW_FILE", {"file_path": "brain/circuit_breaker.py", "end": 3}),
        ("DEVICE_PRESENTATION", {"target": "https://kilo.ai"}),
        ("CHECK_OVERDUE", {}),
        ("SCRAPE_JOBS", {"query": "AI Engineer", "limit": 1}),
    ]

    for intent, payload in auto_tests:
        try:
            result = await orch.auto_dispatch(intent, payload)
            err_short = result.error[:80] if result.error else "none"
            status_icon = "OK" if result.status == "COMPLETED" else "FAI"
            print(f"  [{status_icon}] {intent:25} | status={result.status} | err={err_short}")
            if result.status != "COMPLETED":
                all_passed = False
        except Exception as e:
            print(f"  [EXC] {intent:25} | EXCEPTION: {type(e).__name__}: {e}")
            all_passed = False

    print()
    print("=== Test 4: Bad Action Should Failover Gracefully ===")
    # CHECK_DEVICE is NOT a PCPilot action, but GET_BATTERY is a valid one
    # The registry should translate CHECK_DEVICE -> GET_BATTERY
    result = await orch.dispatch("PCPilot", "CHECK_DEVICE", {}, timeout=30)
    print(f"  PCPilot CHECK_DEVICE -> status={result.status} | (should be COMPLETED via translation to GET_BATTERY)")
    if result.status != "COMPLETED":
        all_passed = False

    print()
    print("=== Test 5: Truly Unsupported Action ===")
    result = await orch.dispatch("PCPilot", "FLY_ROCKET", {}, timeout=30)
    print(f"  PCPilot FLY_ROCKET -> status={result.status} | error={result.error[:100]}")
    if result.status != "FAILED":
        all_passed = False

    print()
    print("SWARM HEALTH SNAPSHOT:")
    report = orch.get_status_report()
    for agent, metrics in report["agents"].items():
        print(f"  {agent:20} | status={metrics['status']:10} | calls={metrics['total_calls']} "
              f"failed={metrics['failed_calls']} | circuit={metrics['circuit_breaker']['state']}")

    print()
    print("=" * 60)
    if all_passed:
        print("ALL CONNECTIVITY TESTS PASSED")
    else:
        print("SOME TESTS FAILED — check output above")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all_agents())
