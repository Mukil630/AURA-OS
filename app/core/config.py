"""Configuration management for MUKIL MASTER AGENT using Pydantic Settings."""
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings loaded from environment variables and .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    APP_NAME: str = Field(default="MUKIL MASTER AGENT", description="Application display name")
    ENVIRONMENT: str = Field(default="local", description="local | staging | production")
    API_VERSION: str = Field(default="v1", description="API Version prefix")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")

    # Server Binding
    HOST: str = Field(default="0.0.0.0", description="Server bind host")
    PORT: int = Field(default=8000, description="Server bind port")
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Allowed CORS origin domains"
    )

    # Security & Authentication
    SECRET_KEY: str = Field(
        default="mukil_master_agent_development_secret_key_change_in_prod",
        description="Cryptographic secret key for signing JWT tokens"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="JWT token lifespan in minutes (default: 24 hours)"
    )
    API_KEY_HEADER_NAME: str = Field(
        default="X-API-Key",
        description="Header name for API key authentication"
    )

    # Database Configuration (Defaults to SQLite with aiosqlite for zero-config local development)
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/master_agent.db",
        description="SQLAlchemy async database connection URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="Print raw SQL queries to stdout")

    # External Storage & Cloud Vault
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = Field(
        default="1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1",
        description="Master Google Drive Vault Folder ID"
    )

    # PC Worker Authentication Token
    PC_WORKER_AUTH_TOKEN: str = Field(
        default="default_pc_worker_token",
        description="Shared secret for local PC worker secure outbound connection"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of Settings."""
    return Settings()
