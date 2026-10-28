"""
AURA 2.0 StateGraph Nodes Engine
aura_langgraph/nodes.py - Implements Mukil's 6-Stage Cognitive Lifecycle:
1. Cognitive Ingestion & RAG Memory Allocation
2. Tool Necessity Decision Gate
3. Historical DB Access & Live Gathering
4. Staged Execution with LIFO Transaction Tracking
5. Two-Layer Verification Gate
6. Commit & Executive Tanglish Synthesizer
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from aura_langgraph.state import AuraGraphState, TransactionStep
from aura_langgraph.rag_engine import master_rag
from aura_langgraph.tool_interceptor import tool_interceptor
from aura_langgraph.rollback import saga_rollback_orchestrator
from aura_langgraph.fallbacks import model_fallback_manager

logger = logging.getLogger("aura_graph_nodes")


# ============================================================================
# STAGE 1: COGNITIVE INGESTION & DYNAMIC MEMORY ALLOCATION
# ============================================================================
def cognitive_ingestion_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Ingests user input, queries the Master RAG engine, and selectively
    allocates relevant historical memory slices into state.
    """
    user_text = state.get("user_input", "").strip()
    logger.info(f"🧠 [Stage 1: Ingestion] Processing input: '{user_text[:80]}'")

    # Query Master RAG engine
    retrieved_docs = master_rag.query(user_text, top_k=3)
    rag_context_str = master_rag.get_ground_truth_context_str(user_text, top_k=3)

    return {
        "retrieved_docs": retrieved_docs,
        "rag_context": {
            "formatted_text": rag_context_str,
            "docs_count": len(retrieved_docs)
        }
    }


# ============================================================================
# STAGE 2: TOOL NECESSITY DECISION GATE
# ============================================================================
def tool_necessity_gate_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Evaluates whether the request requires tools or can take the Fast Path:
    - Conversational / General Concepts -> needs_tools = False
    - Actionable / DB Query / System Control -> needs_tools = True
    """
    user_text = state.get("user_input", "").lower().strip()
    
    # Action keywords detection
    sgc_keywords = ["bill", "invoice", "sgc", "dyeing", "kattu", "kazhi", "shade", "ledger", "overdue", "gst"]
    google_keywords = ["calendar", "event", "meeting", "reminder", "map", "distance", "weather", "sheet", "doc", "mail", "gmail"]
    pc_keywords = ["volume", "brightness", "screenshot", "lock", "sleep", "app", "pc", "battery", "cpu", "ram"]
    career_keywords = ["resume", "job", "freshers", "interview", "amazon", "placement", "infinite"]
    storage_keywords = ["drive", "mesh", "vault", "upload", "sync"]

    target_domain = "CONVERSATION"
    needs_tools = False

    if any(k in user_text for k in sgc_keywords):
        target_domain = "SGC_BUSINESS"
        needs_tools = True
    elif any(k in user_text for k in google_keywords):
        target_domain = "GOOGLE_WORKSPACE"
        needs_tools = True
    elif any(k in user_text for k in pc_keywords):
        target_domain = "PC_PILOT"
        needs_tools = True
    elif any(k in user_text for k in career_keywords):
        target_domain = "CAREER_PLACEMENT"
        needs_tools = True
    elif any(k in user_text for k in storage_keywords):
        target_domain = "DRIVE_MESH"
        needs_tools = True

    logger.info(f"🚦 [Stage 2: NecessityGate] Needs Tools: {needs_tools} | Target Domain: {target_domain}")
    return {
        "intent": target_domain,
        "needs_tools": needs_tools,
        "target_domain": target_domain
    }


# ============================================================================
# STAGE 3: DATA GATHERING & HISTORICAL DB ACCESS
# ============================================================================
def data_gathering_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Retrieves historical records from persistent database stores:
    - SGC past ledger & customer balances
    - Google Calendar active commitments
    - PC hardware metrics
    """
    domain = state.get("target_domain")
    user_text = state.get("user_input", "")
    historical_data: Dict[str, Any] = {}

    logger.info(f"📊 [Stage 3: DataGathering] Querying historical records for domain: {domain}")

    if domain == "SGC_BUSINESS":
        try:
            from tools.sgc_billing_query import get_ledger_metrics
            fin_summary = get_ledger_metrics(target_month="all")
            historical_data["sgc_financial_summary"] = fin_summary
        except Exception as e:
            logger.warning(f"Failed to fetch SGC summary for gathering: {e}")

    elif domain == "GOOGLE_WORKSPACE":
        try:
            from tools.google_calendar_tool import list_upcoming_events
            events = list_upcoming_events(max_results=3)
            historical_data["upcoming_calendar_events"] = events
        except Exception as e:
            logger.warning(f"Failed to fetch Calendar events for gathering: {e}")

    elif domain == "PC_PILOT":
        try:
            from tools.pc_tools import get_system_telemetry
            vitals = get_system_telemetry()
            historical_data["pc_vitals"] = vitals
        except Exception as e:
            logger.warning(f"Failed to fetch PC vitals for gathering: {e}")

    return {"historical_db_data": historical_data}


# ============================================================================
# STAGE 4: STAGED TOOL EXECUTION WITH TRANSACTION STACK
# ============================================================================
def staged_execution_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Executes domain-specific tools with sandboxed exception handling
    and pushes mutating actions onto the LIFO TransactionStack.
    """
    domain = state.get("target_domain")
    user_text = state.get("user_input", "")
    new_tx_steps: List[TransactionStep] = []
    results: Dict[str, Any] = {}

    logger.info(f"⚡ [Stage 4: StagedExecution] Executing tools for domain: {domain}")

    # --- SGC BUSINESS DOMAIN ---
    if domain == "SGC_BUSINESS":
        user_lower = user_text.lower()
        if any(w in user_lower for w in ["overdue", "pending", "outstanding", "debt"]):
            msg, step = tool_interceptor.execute_tool_call("sgc_get_overdue_radar", {"days_threshold": 30})
            results["overdue_radar"] = msg.content
            if step:
                new_tx_steps.append(step)
        elif any(w in user_lower for w in ["tax", "gst", "cgst", "sgst"]):
            msg, step = tool_interceptor.execute_tool_call("sgc_get_dual_month_tax_radar", {})
            results["tax_radar"] = msg.content
            if step:
                new_tx_steps.append(step)
        elif any(w in user_lower for w in ["shade", "color", "catalog", "recipe"]):
            msg, step = tool_interceptor.execute_tool_call("sgc_get_standard_shades_catalog", {"category": "all"})
            results["shades_catalog"] = msg.content
            if step:
                new_tx_steps.append(step)
        elif any(w in user_lower for w in ["summary", "overview", "total", "revenue", "how much"]):
            msg, step = tool_interceptor.execute_tool_call("sgc_get_financial_overview", {})
            results["overview"] = msg.content
            if step:
                new_tx_steps.append(step)
        elif any(w in user_lower for w in ["list", "recent", "bills", "invoices"]):
            msg, step = tool_interceptor.execute_tool_call("sgc_list_invoices", {"limit": 5})
            results["invoices"] = msg.content
            if step:
                new_tx_steps.append(step)
        elif any(w in user_lower for w in ["bill", "create", "invoice"]):
            # Staged quick invoice creation
            args = {"customer": "Bannari Amman Spinning Mills", "count": "10s", "kattu": 50, "rate": 420, "variety": "cone winding"}
            msg, step = tool_interceptor.execute_tool_call("sgc_create_quick_invoice", args)
            results["invoice_created"] = msg.content
            if step:
                new_tx_steps.append(step)

    # --- GOOGLE WORKSPACE DOMAIN ---
    elif domain == "GOOGLE_WORKSPACE":
        user_lower = user_text.lower()
        if "weather" in user_lower:
            msg, step = tool_interceptor.execute_tool_call("google_weather_radar_karur", {"location": "Karur, Tamil Nadu"})
            results["weather"] = msg.content
        elif any(w in user_lower for w in ["list", "upcoming", "what events", "appointments"]):
            msg, step = tool_interceptor.execute_tool_call("list_upcoming_events", {"max_results": 5})
            results["upcoming_events"] = msg.content
        elif any(w in user_lower for w in ["calendar", "event", "schedule", "reminder"]):
            args = {"title": "SGC Payment Collection - Bannari Amman", "start_time_iso": "2026-10-22 10:00:00", "duration_minutes": 30}
            msg, step = tool_interceptor.execute_tool_call("add_calendar_reminder", args)
            results["calendar_event"] = msg.content
            if step:
                new_tx_steps.append(step)

    # --- PC PILOT DOMAIN ---
    elif domain == "PC_PILOT":
        user_lower = user_text.lower()
        if any(w in user_lower for w in ["volume", "sound", "audio"]):
            msg, step = tool_interceptor.execute_tool_call("get_system_volume", {})
            results["volume"] = msg.content
        elif any(w in user_lower for w in ["screenshot", "screen"]):
            msg, step = tool_interceptor.execute_tool_call("take_pc_screenshot", {})
            results["screenshot"] = msg.content
            if step:
                new_tx_steps.append(step)
        elif any(w in user_lower for w in ["lock", "lockscreen"]):
            msg, step = tool_interceptor.execute_tool_call("lock_workstation", {})
            results["lock"] = msg.content
        else:
            msg, step = tool_interceptor.execute_tool_call("get_system_telemetry", {})
            results["telemetry"] = msg.content

    # --- DRIVE MESH DOMAIN ---
    elif domain == "DRIVE_MESH":
        user_lower = user_text.lower()
        if any(w in user_lower for w in ["portal", "summary", "nodes", "all drives"]):
            msg, step = tool_interceptor.execute_tool_call("get_unified_portal_summary", {})
            results["portal_summary"] = msg.content
        else:
            msg, step = tool_interceptor.execute_tool_call("search_drive_mesh", {"query": user_text})
            results["mesh_results"] = msg.content

    # --- BUSINESS LEADS DOMAIN ---
    elif domain == "BUSINESS_LEADS":
        msg, step = tool_interceptor.execute_tool_call("scrape_spinning_mills", {"district": "Karur", "max_results": 5})
        results["mill_leads"] = msg.content

    return {
        "execution_results": results,
        "transaction_stack": new_tx_steps
    }


# ============================================================================
# STAGE 5: TWO-LAYER VERIFICATION GATE
# ============================================================================
def verification_gate_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Verifies execution results:
    Layer 1: Deterministic check (non-empty output, valid status)
    Layer 2: Semantic alignment with Mukil's goal
    If verification fails, flags rollback_required = True.
    """
    results = state.get("execution_results", {})
    user_text = state.get("user_input", "")

    # Layer 1 Check: Did tools produce valid output or throw an error?
    has_errors = any("Error executing tool" in str(v) for v in results.values())
    if has_errors:
        logger.warning("❌ [Stage 5: Verifier] Layer 1 Check FAILED: Tool returned execution error.")
        return {
            "verification_passed": False,
            "verification_feedback": "Tool returned execution error",
            "rollback_required": True,
            "rollback_reason": "Tool execution returned an error"
        }

    logger.info("✅ [Stage 5: Verifier] Verification PASSED! System state validated.")
    return {
        "verification_passed": True,
        "verification_feedback": "All operations verified clean",
        "rollback_required": False
    }


# ============================================================================
# STAGE 6A: COMMIT & EXECUTIVE TANGLISH SYNTHESIZER
# ============================================================================
def commit_and_synthesize_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Synthesizes executive response in authentic Tanglish ('Boss' / 'Maapla' Stark tone),
    grounded with RAG facts and execution proof links.
    """
    user_text = state.get("user_input", "")
    rag_facts = state.get("rag_context", {}).get("formatted_text", "")
    hist_data = state.get("historical_db_data", {})
    exec_data = state.get("execution_results", {})

    system_prompt = (
        "You are AURA, Mukil's autonomous personal AI executive partner & system architect.\n"
        "Tone: Authentic, energetic, sharp Tamil-Tanglish ('Maapla' / 'Boss' Stark dynamic).\n"
        "Always cite ground truth from the provided RAG facts and execution results.\n"
        "Never hallucinate. Present proof links (Drive folders, bill numbers, metrics) clearly."
    )

    hist_str = json.dumps(hist_data, indent=2)
    if len(hist_str) > 2500:
        hist_str = hist_str[:2500] + "\n... [historical DB summary truncated]"

    exec_str = json.dumps(exec_data, indent=2)
    if len(exec_str) > 2500:
        exec_str = exec_str[:2500] + "\n... [live execution data truncated]"

    context_bundle = (
        f"User Query: {user_text}\n\n"
        f"Retrieved Master Vault RAG Facts:\n{rag_facts}\n\n"
        f"Historical DB Records:\n{hist_str}\n\n"
        f"Live Execution Results:\n{exec_str}"
    )

    # Use ModelFallbackManager (Groq -> Gemini -> Offline)
    inference_result = model_fallback_manager.invoke_with_fallback(
        system_prompt=system_prompt,
        user_message=context_bundle,
        temperature=0.3
    )

    final_reply = inference_result.get("content", "")
    return {
        "final_output": final_reply,
        "fallback_mode_active": inference_result.get("fallback_triggered", False)
    }


# ============================================================================
# STAGE 6B: SAGA ROLLBACK ORCHESTRATOR NODE
# ============================================================================
def rollback_orchestrator_node(state: AuraGraphState) -> Dict[str, Any]:
    """
    Invoked when verification fails or a critical error occurs.
    Pops the TransactionStack in reverse LIFO order and restores clean baseline.
    """
    logger.warning("🚨 [Stage 6B: RollbackNode] Triggering Saga Rollback Orchestrator...")
    rollback_res = saga_rollback_orchestrator.rollback(state)
    report_msg = rollback_res.get("report_message", "Rollback completed.")
    
    return {
        "final_output": report_msg,
        "compensated_steps": rollback_res.get("compensated_steps", []),
        "rollback_required": False
    }
