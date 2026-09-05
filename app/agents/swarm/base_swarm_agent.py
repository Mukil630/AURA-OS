"""Base Swarm Agent specification for AURA-OS.
Defines strongly typed event dispatching, peer-to-peer messaging, and task logging.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class SwarmTaskMessage(BaseModel):
    task_id: str
    sender: str
    recipient: str
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = "PENDING"  # "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseSwarmAgent(ABC):
    """Abstract base for all specialized autonomous worker agents in the AURA Swarm."""

    def __init__(self, agent_name: str, role_description: str):
        self.agent_name = agent_name
        self.role_description = role_description

    @abstractmethod
    async def process_task(self, message: SwarmTaskMessage) -> SwarmTaskMessage:
        """Process an assigned task and return the updated message with results."""
        pass
