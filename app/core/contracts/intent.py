"""Version 1 Data Contracts for Intent Understanding, Entity Extraction, and Task Context."""
from typing import Any, Dict, List, Optional
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    ChannelType,
    IntentCategory,
    RiskLevel,
    TaskType,
)


class ExtractedEntitiesContract(VersionedContractBase):
    """Structured entities parsed out of natural language user requests."""
    time: Optional[str] = Field(default=None, description="Extracted time (e.g. '09:00', '14:30')")
    relative_day: Optional[str] = Field(default=None, description="Extracted day context (e.g. 'tomorrow', 'today', 'monday')")
    date: Optional[str] = Field(default=None, description="Extracted ISO date string")
    subject: Optional[str] = Field(default=None, description="Core topic or task payload (e.g. 'study Java')")
    target_repo: Optional[str] = Field(default=None, description="Target repository (e.g. 'Mukil630/AURA-OS')")
    file_path: Optional[str] = Field(default=None, description="Target file path or artifact name")
    recipient: Optional[str] = Field(default=None, description="Target recipient (e.g. '@mukil', chat_id)")
    query_text: Optional[str] = Field(default=None, description="Search or information query string")
    custom_entities: Dict[str, Any] = Field(default_factory=dict, description="Domain-specific key-value extractions")


class ParsedIntentContract(VersionedContractBase):
    """
    Structured outcome of the Natural Language Understanding & Intent Classification stage.
    Answers: WHAT does the user want, and WHAT capabilities will be needed?
    """
    raw_input: str = Field(..., description="Original raw user input text")
    normalized_input: str = Field(..., description="Cleaned, standardized text")
    intent: IntentCategory = Field(..., description="Classified intent category")
    task_type: TaskType = Field(..., description="Functional task classification")
    required_capabilities: List[str] = Field(
        default_factory=list,
        description="List of capability slugs needed to execute this request (e.g. ['github.read_ci'])"
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Intrinsic risk level of this request")
    extracted_entities: ExtractedEntitiesContract = Field(
        default_factory=ExtractedEntitiesContract,
        description="Structured entity slots parsed from request"
    )
    confidence_score: float = Field(default=0.9, ge=0.0, le=1.0, description="Classification confidence (0.0 to 1.0)")
    ambiguity_detected: bool = Field(default=False, description="True if input is underspecified or requires clarification")
    suggested_clarification: Optional[str] = Field(default=None, description="Question to ask user if ambiguous")


class NormalizedTaskContext(VersionedContractBase):
    """
    Complete context package prepared by Master Agent for the Task Planner.
    """
    task_id: str = Field(..., description="Associated Task ID")
    user_id: str = Field(..., description="Owner User ID")
    channel: ChannelType = Field(default=ChannelType.API, description="Originating channel")
    parsed_intent: ParsedIntentContract = Field(..., description="Structured intent analysis")
    context_metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual variables and session state")
