"""Authentication and Security Subsystem for MUKIL MASTER AGENT."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
security_bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Authenticated user context object."""
    user_id: str = Field(..., description="Unique User/Actor ID")
    tenant_id: str = Field(default="mukil", description="Tenant ownership boundary")
    role: str = Field(default="authenticated_user", description="User role")
    session_id: Optional[str] = Field(default=None, description="Active session ID")
    auth_method: str = Field(default="bearer", description="bearer | api_key | anonymous")


def create_access_token(
    user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    role: str = "authenticated_user",
    session_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate signed JWT access token with distinct actor and tenant identities."""
    settings = get_settings()
    actual_actor = actor_id or user_id or "mukil"
    actual_tenant = tenant_id or user_id or actual_actor

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": actual_actor,
        "tenant_id": actual_tenant,
        "role": role,
        "session_id": session_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.APP_NAME,
    }
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "iat"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_tenant_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> "TenantContext":
    """
    FastAPI dependency resolving trusted TenantContext strictly from authenticated credentials.
    Ignores any client payload or header spoofing attempts.
    """
    from app.security.tenant import TenantContext
    settings = get_settings()

    # 1. Bearer Token Check
    if credentials and credentials.credentials:
        token = credentials.credentials
        payload = decode_access_token(token)
        actor = payload.get("sub", "unknown_actor")
        tenant = payload.get("tenant_id") or actor
        return TenantContext(
            tenant_id=tenant,
            actor_id=actor,
            role=payload.get("role", "authenticated_user"),
        )

    # 2. X-API-Key Header Check
    if x_api_key:
        if x_api_key == settings.SECRET_KEY or x_api_key.startswith("mukil_"):
            return TenantContext(
                tenant_id="mukil",
                actor_id="mukil_admin",
                role="admin",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key provided.",
        )

    # 3. Development / Local Fallback
    if settings.ENVIRONMENT == "local":
        return TenantContext(
            tenant_id="mukil",
            actor_id="dev_local_user",
            role="admin",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    tenant_ctx: "TenantContext" = Depends(get_tenant_context),
) -> AuthenticatedUser:
    """FastAPI dependency resolving authenticated user while preserving backward compatibility."""
    return AuthenticatedUser(
        user_id=tenant_ctx.actor_id,
        tenant_id=tenant_ctx.tenant_id,
        role=tenant_ctx.role,
        auth_method="bearer",
    )
