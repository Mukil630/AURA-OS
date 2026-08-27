"""Unit tests for JWT Authentication Utilities."""
from datetime import timedelta
import pytest
from fastapi import HTTPException
from app.security.auth import create_access_token, decode_access_token


def test_jwt_create_and_decode():
    token = create_access_token(user_id="mukil_007", role="admin", session_id="sess_123")
    payload = decode_access_token(token)
    assert payload["sub"] == "mukil_007"
    assert payload["role"] == "admin"
    assert payload["session_id"] == "sess_123"


def test_jwt_expired_token():
    # Create an already expired token
    token = create_access_token(
        user_id="mukil_007",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_jwt_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("invalid.token.string")
    assert exc_info.value.status_code == 401
