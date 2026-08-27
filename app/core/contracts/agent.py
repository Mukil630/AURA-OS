"""Version 1 Data Contracts for Specialist Agents and Capabilities."""
from typing import List, Optional
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    AgentStatus,
    AgentType,
    RiskLevel,
)


class AgentCapabilityContract(VersionedContractBase):
    """
    Contract defining a specific semantic capability owned by an agent.
    Master Agent discovers capabilities dynamically via the Agent Registry.
    """
    capability_id: str = Field(..., description="Unique slug for capability (e.g. 'github.read_ci').")
    name: str = Field(..., description="Human-readable capability name.")
    description: str = Field(..., description="Clear description of what this capability achieves.")
    required_tools: List[str] = Field(default_factory=list, description="Tools required to execute this capability.")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Intrinsic risk level of this capability.")


class AgentContract(VersionedContractBase):
    """
    Contract defining a Specialist Agent registered in the OS.
    An Agent is a reasoning/capability owner that knows how to utilize tools.
    """
    agent_id: str = Field(..., description="Unique slug for the agent (e.g. 'github_agent').")
    name: str = Field(..., description="Display name of the agent (e.g. 'GitHub Specialist Agent').")
    agent_type: AgentType = Field(..., description="Standardized classification of the agent.")
    description: str = Field(..., description="Overview of the agent's domain expertise and purpose.")
    version: str = Field(default="1.0.0", description="Semantic version of the agent definition.")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="Current operational state.")
    capabilities: List[AgentCapabilityContract] = Field(
        default_factory=list,
        description="Declared capabilities exposed by this agent."
    )
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="Whitelist of tool IDs this agent has permission to invoke."
    )
    max_concurrency: int = Field(
        default=5,
        gt=0,
        description="Maximum concurrent executions allowed for this agent."
    )
    system_prompt_ref: Optional[str] = Field(
        default=None,
        description="Reference or path to the agent's specialized reasoning instructions."
    )
    health_status: str = Field(
        default="healthy",
        description="Health report summary string."
    )
