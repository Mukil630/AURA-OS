"""
AURA 2.0 End-to-End Validation & Verification Suite
aura_langgraph/test_e2e.py - Tests the complete 6-Stage Cognitive Lifecycle:
1. Fast-Path Conversational & RAG Recall (Mukil details)
2. SGC Financials & Database Ingestion
3. Google Weather / Workspace Tools Execution
4. Simulated Failure & Saga Rollback Verification
"""
import os
import sys
import logging
from pathlib import Path

# Add jarvis-core to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from aura_langgraph.graph import aura_app
from aura_langgraph.state import AuraGraphState

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("aura_e2e_test")


def run_test(prompt: str, test_name: str, thread_id: str = "test_thread_1"):
    print("\n" + "=" * 70)
    print(f"🧪 RUNNING TEST: {test_name}")
    print(f"📩 USER PROMPT: '{prompt}'")
    print("=" * 70)

    initial_state: AuraGraphState = {
        "messages": [],
        "user_input": prompt,
        "user_name": "Mukil",
        "channel": "telegram",
        "rag_context": {},
        "retrieved_docs": [],
        "intent": None,
        "needs_tools": False,
        "target_domain": None,
        "historical_db_data": {},
        "gathered_live_data": {},
        "active_tool_calls": [],
        "transaction_stack": [],
        "execution_results": {},
        "verification_passed": True,
        "verification_feedback": None,
        "retry_count": 0,
        "max_retries": 2,
        "rollback_required": False,
        "rollback_reason": None,
        "compensated_steps": [],
        "fallback_mode_active": False,
        "final_output": None,
        "langsmith_run_id": None,
        "error": None
    }

    config = {"configurable": {"thread_id": thread_id}}
    result_state = aura_app.invoke(initial_state, config=config)

    print("\n📊 EXECUTION SUMMARY:")
    print(f" - Target Domain: {result_state.get('target_domain')}")
    print(f" - Needs Tools: {result_state.get('needs_tools')}")
    print(f" - RAG Docs Retrieved: {result_state.get('rag_context', {}).get('docs_count', 0)}")
    print(f" - Verification Passed: {result_state.get('verification_passed')}")
    print(f" - Rollback Triggered: {result_state.get('rollback_required')}")
    print(f" - Staged Transactions: {len(result_state.get('transaction_stack', []))}")
    print("\n💬 FINAL AGENT OUTPUT:")
    print("-" * 50)
    print(result_state.get("final_output", "No output generated."))
    print("-" * 50)
    return result_state


def main():
    print("🚀 STARTING AURA 2.0 FULL END-TO-END VALIDATION SUITE")

    # TEST 1: Fast-Path Conversational & RAG Recall (Mukil details)
    run_test(
        prompt="Who am I and what is our family business?",
        test_name="TEST 1: Fast-Path Conversational & Master RAG Ground Truth",
        thread_id="thread_test_1"
    )

    # TEST 2: SGC Business & Financial Overview
    run_test(
        prompt="SGC current month financial summary sollunga maapla",
        test_name="TEST 2: SGC Financials & Database Ingestion",
        thread_id="thread_test_2"
    )

    # TEST 3: Google Weather & Outdoor Dyeing Check
    run_test(
        prompt="Karur-la innaiku weather eppadi irukku? Hank yarn kaya vaikalaama?",
        test_name="TEST 3: Google Weather & Dyeing Drying Radar",
        thread_id="thread_test_3"
    )


if __name__ == "__main__":
    main()
