"""Authentication endpoints."""
from datetime import timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.security.auth import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenRequest(BaseModel):
    """Token generation request."""
    user_id: str = Field(..., description="User ID requesting authentication")
    role: str = Field(default="authenticated_user", description="User role")
    session_id: str | None = Field(default=None, description="Optional session ID")


class TokenResponse(BaseModel):
    """JWT Token response."""
    access_token: str = Field(..., description="Signed JWT Bearer token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in_seconds: int = Field(..., description="Token lifespan in seconds")
    user_id: str = Field(..., description="Authenticated user ID")


@router.post("/token", response_model=TokenResponse)
async def generate_token(payload: TokenRequest) -> TokenResponse:
    """Generate a signed JWT access token for client authentication."""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        user_id=payload.user_id,
        role=payload.role,
        session_id=payload.session_id,
        expires_delta=expires_delta,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires_delta.total_seconds()),
        user_id=payload.user_id,
    )


@router.get("/me", response_model=AuthenticatedUser)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Return identity and claims of current authenticated client."""
    return current_user
