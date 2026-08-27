"""Abstract Interface definitions for External Connectors and Capability Dispatch."""
from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.contracts.connector import (
    CapabilityContract,
    ConnectorContract,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorHealthContract,
)
from app.core.enums import ConnectorType


class IConnector(ABC):
    """
    Abstract interface for all external system connectors (e.g. GitHub, Google, Telegram, PC Worker).
    """
    @property
    @abstractmethod
    def connector_id(self) -> str:
        """Unique identifier of the connector."""
        pass

    @property
    @abstractmethod
    def connector_type(self) -> ConnectorType:
        """Connector provider type classification."""
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection / authenticate with the remote service."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully terminate connection and clean up resources."""
        pass

    @abstractmethod
    async def health_check(self) -> ConnectorHealthContract:
        """Perform diagnostic health probe and return structured health status."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the connector is currently active and authenticated."""
        pass

    @abstractmethod
    def get_contract(self) -> ConnectorContract:
        """Return metadata contract describing supported capabilities and scopes."""
        pass

    @abstractmethod
    def list_capabilities(self) -> List[CapabilityContract]:
        """Return list of discrete capabilities offered by this connector."""
        pass

    @abstractmethod
    async def execute_capability(
        self,
        request: ConnectorExecutionRequest,
        credentials: Optional[str] = None,
    ) -> ConnectorExecutionResult:
        """
        Execute a capability against the remote provider with injected credentials.
        """
        pass


class IConnectorRegistry(ABC):
    """Central registry interface for managing active connectors."""
    @abstractmethod
    def register_connector(self, connector: IConnector) -> None:
        """Register an active connector."""
        pass

    @abstractmethod
    def get_connector(self, connector_id: str) -> Optional[IConnector]:
        """Retrieve connector by ID."""
        pass

    @abstractmethod
    def list_connectors(self) -> List[ConnectorContract]:
        """List all registered connectors and their health states."""
        pass
