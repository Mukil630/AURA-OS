"""
AURA 2.0 LangGraph State Specification
aura_langgraph/state.py - Typed schema definition for stateful graph execution,
transactional compensation stacks, RAG context, and verification gates.
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator
from langchain_core.messages import BaseMessage


class TransactionStep(TypedDict):
    """Represents a reversible state-mutating tool operation in the Saga transaction stack."""
    step_id: str
    tool_name: str
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    compensating_tool: Optional[str]
    compensating_args: Optional[Dict[str, Any]]
    status: str  # "STAGED", "COMMITTED", "COMPENSATED", "FAILED"
    is_reversible: bool
    timestamp: str


class RagDocument(TypedDict):
    """A retrieved knowledge chunk from Mukil's master vault."""
    doc_id: str
    category: str  # "profile", "sgc_business", "placement", "drive_mesh", "credentials"
    title: str
    content: str
    score: float


class AuraGraphState(TypedDict):
    """
    Central State Object for AURA 2.0 LangGraph Engine.
    Carries user intent, selective memory, RAG facts, tool execution results,
    and the Saga rollback stack through the cyclic state machine.
    """
    # 1. Message & Channel Context
    messages: Annotated[List[BaseMessage], operator.add]
    user_input: str
    user_name: str
    channel: str  # "telegram", "cli", "mobile_pwa", "voice"
    
    # 2. Stage 1: RAG & Selective Memory Allocation
    rag_context: Dict[str, Any]
    retrieved_docs: List[RagDocument]
    
    # 3. Stage 2: Intent & Tool Necessity Gate
    intent: Optional[str]  # "CONVERSATION", "SGC_BUSINESS", "GOOGLE_WORKSPACE", "PC_PILOT", "CAREER", "STORAGE", "TURSO"
    needs_tools: bool
    target_domain: Optional[str]
    
    # 4. Stage 3: Historical DB & Live Gathered Data
    historical_db_data: Dict[str, Any]
    gathered_live_data: Dict[str, Any]
    
    # 5. Stage 4: Staged Execution & Saga Transaction Stack
    active_tool_calls: List[Dict[str, Any]]
    transaction_stack: Annotated[List[TransactionStep], operator.add]
    execution_results: Dict[str, Any]
    
    # 6. Stage 5: Two-Layer Verification
    verification_passed: bool
    verification_feedback: Optional[str]
    retry_count: int
    max_retries: int
    
    # 7. Stage 6: Rollback & Error State
    rollback_required: bool
    rollback_reason: Optional[str]
    compensated_steps: List[str]
    fallback_mode_active: bool
    error: Optional[str]
    
    # 8. Output & Telemetry
    final_output: Optional[str]
    langsmith_run_id: Optional[str]
