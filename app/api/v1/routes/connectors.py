"""Connector Management and Capability Registry API Endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.connectors.credential_manager import CredentialManager
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.github.connector import GitHubConnector
from app.connectors.pc_sidecar.connector import WindowsSidecarConnector
from app.connectors.policy import default_policy_engine
from app.connectors.router import CapabilityRouter
from app.connectors.telegram.connector import TelegramConnector
from app.core.contracts.connector import (
    CapabilityContract,
    ConnectorContract,
    ConnectorHealthContract,
    CredentialContract,
)
from app.core.enums import ConnectorType
from app.security.auth import AuthenticatedUser, get_current_user


router = APIRouter(prefix="/connectors", tags=["External Connectors"])

# Global Singleton Router Instance
_cred_mgr = CredentialManager()
_policy_engine = default_policy_engine
_capability_router = CapabilityRouter(credential_manager=_cred_mgr, policy_engine=_policy_engine)

_github_conn = GitHubConnector()
_drive_conn = GoogleDriveConnector()
_telegram_conn = TelegramConnector()
_pc_conn = WindowsSidecarConnector()

_capability_router.register_connector(_github_conn)
_capability_router.register_connector(_drive_conn)
_capability_router.register_connector(_telegram_conn)
_capability_router.register_connector(_pc_conn)


class SetCredentialRequest(BaseModel):
    """Payload to register a provider API key securely."""
    provider: ConnectorType = Field(..., description="Provider type (github, google_drive, telegram, etc.)")
    token: str = Field(..., min_length=4, description="Secret token string.")


class KillSwitchRequest(BaseModel):
    """Payload to trigger kill-switch on connector."""
    connector_id: str = Field(..., description="Connector identifier.")
    enabled: bool = Field(..., description="Set false to trigger emergency stop.")


@router.get(
    "",
    response_model=List[ConnectorContract],
    summary="List all registered external connectors",
    description="Returns metadata contracts of all active connectors and their status.",
)
async def list_connectors(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[ConnectorContract]:
    """List connectors."""
    return _capability_router.list_connectors()


@router.get(
    "/capabilities",
    response_model=List[CapabilityContract],
    summary="List all available capabilities",
    description="Returns list of registered atomic capabilities across all connectors.",
)
async def list_capabilities(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[CapabilityContract]:
    """List capabilities."""
    return _capability_router.list_capabilities()


@router.get(
    "/{connector_id}/health",
    response_model=ConnectorHealthContract,
    summary="Probe health of specific connector",
    description="Executes health check against the connector endpoint.",
)
async def check_connector_health(
    connector_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConnectorHealthContract:
    """Check health."""
    conn = _capability_router.get_connector(connector_id)
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found.",
        )
    return await conn.health_check()


@router.post(
    "/credentials",
    response_model=CredentialContract,
    summary="Store provider credentials securely",
    description="Stores token in isolated credential manager and returns safe masked contract.",
)
async def store_credential(
    payload: SetCredentialRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CredentialContract:
    """Store credential."""
    return _cred_mgr.set_credential(
        provider=payload.provider,
        token=payload.token,
        user_id=current_user.user_id,
    )


@router.post(
    "/kill-switch",
    summary="Toggle emergency kill-switch for a connector",
    description="Emergency stop to immediately halt all network dispatches to a connector.",
)
async def toggle_kill_switch(
    payload: KillSwitchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Toggle kill-switch."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privilege required to toggle kill-switch.",
        )

    if payload.enabled:
        _policy_engine.enable_connector(payload.connector_id)
        msg = f"Connector '{payload.connector_id}' enabled."
    else:
        _policy_engine.disable_connector(payload.connector_id)
        msg = f"EMERGENCY STOP: Connector '{payload.connector_id}' disabled."

    return {"connector_id": payload.connector_id, "is_enabled": payload.enabled, "message": msg}
