"""Comprehensive Test Suite for 6-Stage Master Cognitive Engine."""
import asyncio
import pytest
from app.brain.intent_classifier import IntentClassifier, IntentType
from app.brain.context_hydrator import ContextHydrator
from app.brain.clarification_gate import ClarificationGate, RiskTier
from app.brain.dag_planner import DAGPlanner, ExecutionPlan, PlanStep
from app.brain.saga_rollback_engine import SAGARollbackEngine, StepStatus
from app.brain.master_orchestrator import MasterOrchestrator


def test_01_intent_classification_single_and_compound():
    classifier = IntentClassifier()

    # Pure Conversation
    res1 = classifier.classify("Hello maapla, how are you?")
    assert res1.primary_intent == IntentType.CONVERSATION

    # Pure Task
    res2 = classifier.classify("open youtube and check battery")
    assert res2.primary_intent == IntentType.TASK
    assert len(res2.sub_intents) >= 1

    # Compound Intent (Convo + Task)
    res3 = classifier.classify("Hi maapla, also scrape this website https://example.com")
    assert res3.primary_intent == IntentType.TASK
    assert len(res3.sub_intents) >= 2


def test_02_context_hydration():
    hydrator = ContextHydrator()
    ctx = hydrator.hydrate(max_recent_tasks=3)
    assert ctx.user_name in ["Mukil", "MUKILARASU S"]
    assert "IST" in ctx.system_time_ist
    
    prompt = hydrator.format_system_prompt_context(ctx)
    assert "MUKIL MASTER CONTEXT" in prompt


def test_03_clarification_gate_risk_tiers():
    gate = ClarificationGate()

    # Tier 1 Safe Read
    dec1 = gate.evaluate_intent("check laptop battery status")
    assert not dec1.requires_clarification
    assert dec1.risk_tier == RiskTier.TIER_1_READ_ONLY

    # Tier 3 Destructive Action
    dec2 = gate.evaluate_intent("delete all customer bills and drop database")
    assert dec2.requires_clarification
    assert dec2.risk_tier == RiskTier.TIER_3_HIGH_RISK
    assert "Confirm panna proceed pannatuma" in dec2.clarification_prompt


def test_04_dag_planner_generation():
    planner = DAGPlanner()
    plan = planner.create_plan("scrape and analyze product table from https://example.com")
    assert len(plan.steps) >= 3
    assert plan.steps[0].name == "Fetch Web Content"
    assert plan.steps[1].name == "Analyze & Summarize"


def test_05_saga_rollback_engine_success_and_failure():
    async def run_test():
        # Success Path
        engine = SAGARollbackEngine()
        planner = DAGPlanner()
        plan = planner.create_plan("open chrome browser")
        results = await engine.execute_plan(plan)
        assert len(results) == len(plan.steps)
        assert all(r.status == StepStatus.SUCCESS for r in results)

        # Failure & Rollback Path
        rollback_tracker = []
        
        async def mock_failing_executor(tool_name: str, args: dict):
            if tool_name == "analyze_content":
                raise RuntimeError("Network Timeout 504")
            if "delete" in tool_name or "rollback" in tool_name:
                rollback_tracker.append(tool_name)
            return {"status": "ok"}

        fail_engine = SAGARollbackEngine(tool_executor=mock_failing_executor)
        fail_plan = ExecutionPlan(
            goal="Test Rollback",
            steps=[
                PlanStep(order=1, name="Step 1 Temp File", tool_name="create_temp", is_compensable=True, compensating_action="delete_temp"),
                PlanStep(order=2, name="Step 2 Network", tool_name="analyze_content", is_compensable=True),
            ]
        )
        fail_results = await fail_engine.execute_plan(fail_plan)
        assert fail_results[0].status == StepStatus.SUCCESS
        assert fail_results[1].status == StepStatus.FAILED
        # Verify rollback was triggered
        assert "delete_temp" in rollback_tracker

    asyncio.run(run_test())


def test_06_master_orchestrator_end_to_end():
    async def run_test():
        orchestrator = MasterOrchestrator()

        # 1. Conversation Path
        resp1 = await orchestrator.process_user_input("Hi maapla, how are you?")
        assert resp1.response_type == "CONVERSATION"
        assert "Mukil" in resp1.text

        # 2. Clarification Path
        resp2 = await orchestrator.process_user_input("delete all records from memory database")
        assert resp2.response_type == "CLARIFICATION_REQUIRED"
        assert resp2.clarification_decision.risk_tier == RiskTier.TIER_3_HIGH_RISK

        # 3. Task Execution Path
        resp3 = await orchestrator.process_user_input("open youtube and start playlist")
        assert resp3.response_type == "TASK_COMPLETED"
        assert len(resp3.step_results) >= 1
        assert "100% verified" in resp3.text

    asyncio.run(run_test())


def test_07_polyglot_db_and_transactional_outbox(tmp_path):
    async def run_test():
        from app.database.polyglot_manager import PolyglotDBManager, StorageTarget
        
        outbox_file = str(tmp_path / "test_outbox.json")
        manager = PolyglotDBManager(outbox_file=outbox_file)

        # 1. Stage a Google Drive record
        rec = manager.stage_outbox_record(
            target=StorageTarget.CLOUD_DRIVE_VAULT,
            payload={"filename": "SGC_Bill_101.pdf", "customer": "Rajesh"}
        )
        assert manager.get_pending_count() == 1
        assert rec.sync_status == "PENDING"

        # 2. Simulate offline failure
        synced_0 = await manager.flush_outbox(mock_network_success=False)
        assert synced_0 == 0
        assert manager.get_pending_count() == 1

        # 3. Simulate online reconnect
        synced_1 = await manager.flush_outbox(mock_network_success=True)
        assert synced_1 == 1
        assert manager.get_pending_count() == 0

    asyncio.run(run_test())

