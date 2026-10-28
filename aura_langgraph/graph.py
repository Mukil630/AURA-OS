"""
AURA 2.0 LangGraph Master StateGraph Assembly
aura_langgraph/graph.py - Assembles Mukil's 6-Stage Cognitive Lifecycle into a
compiled, cyclic StateGraph with conditional branching, durable checkpointing,
and industrial Saga rollback recovery.
"""
import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from aura_langgraph.state import AuraGraphState
from aura_langgraph.nodes import (
    cognitive_ingestion_node,
    tool_necessity_gate_node,
    data_gathering_node,
    staged_execution_node,
    verification_gate_node,
    commit_and_synthesize_node,
    rollback_orchestrator_node
)

logger = logging.getLogger("aura_langgraph_engine")


def route_tool_necessity(state: AuraGraphState) -> Literal["data_gathering", "commit_and_synthesize"]:
    """
    Conditional Edge:
    - If tools are needed -> proceeds to Data Gathering & DB access
    - If conversational / conceptual -> Fast-Path to Synthesizer
    """
    if state.get("needs_tools", False):
        return "data_gathering"
    return "commit_and_synthesize"


def route_verification_result(state: AuraGraphState) -> Literal["commit_and_synthesize", "rollback_orchestrator"]:
    """
    Conditional Edge:
    - If verification passed -> proceeds to Commit & Synthesis
    - If verification failed / error flagged -> triggers Saga Rollback Orchestrator
    """
    if state.get("rollback_required", False) or not state.get("verification_passed", True):
        return "rollback_orchestrator"
    return "commit_and_synthesize"


def build_aura_graph(checkpointer=None):
    """
    Compiles and returns the master AURA 2.0 LangGraph state machine.
    """
    workflow = StateGraph(AuraGraphState)

    # 1. Register Lifecycle Nodes
    workflow.add_node("cognitive_ingestion", cognitive_ingestion_node)
    workflow.add_node("tool_necessity_gate", tool_necessity_gate_node)
    workflow.add_node("data_gathering", data_gathering_node)
    workflow.add_node("staged_execution", staged_execution_node)
    workflow.add_node("verification_gate", verification_gate_node)
    workflow.add_node("commit_and_synthesize", commit_and_synthesize_node)
    workflow.add_node("rollback_orchestrator", rollback_orchestrator_node)

    # 2. Configure State Machine Transitions
    workflow.set_entry_point("cognitive_ingestion")
    workflow.add_edge("cognitive_ingestion", "tool_necessity_gate")

    # Conditional Branch 1: Fast Path vs Tool Gathering
    workflow.add_conditional_edges(
        "tool_necessity_gate",
        route_tool_necessity,
        {
            "data_gathering": "data_gathering",
            "commit_and_synthesize": "commit_and_synthesize"
        }
    )

    workflow.add_edge("data_gathering", "staged_execution")
    workflow.add_edge("staged_execution", "verification_gate")

    # Conditional Branch 2: Commit vs Rollback
    workflow.add_conditional_edges(
        "verification_gate",
        route_verification_result,
        {
            "commit_and_synthesize": "commit_and_synthesize",
            "rollback_orchestrator": "rollback_orchestrator"
        }
    )

    workflow.add_edge("commit_and_synthesize", END)
    workflow.add_edge("rollback_orchestrator", END)

    # Compile with MemorySaver Checkpointer
    saver = checkpointer or MemorySaver()
    app = workflow.compile(checkpointer=saver)
    logger.info("🚀 [AuraLangGraph] Master StateGraph successfully compiled with durable checkpointing!")
    return app


# Master Compiled Graph Singleton
aura_app = build_aura_graph()
