"""Unit tests for Settings and Configuration."""
from app.core.config import Settings, get_settings


def test_settings_defaults():
    settings = get_settings()
    assert settings.APP_NAME == "MUKIL MASTER AGENT"
    assert settings.API_VERSION == "v1"
    assert settings.ENVIRONMENT in ("local", "staging", "production")
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_custom_settings_override():
    custom = Settings(
        APP_NAME="CUSTOM AGENT",
        ENVIRONMENT="staging",
        DATABASE_ECHO=True,
    )
    assert custom.APP_NAME == "CUSTOM AGENT"
    assert custom.ENVIRONMENT == "staging"
    assert custom.DATABASE_ECHO is True
