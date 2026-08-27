"""Connector types, authentication methods, and connection states."""
from enum import Enum


class ConnectorType(str, Enum):
    """External system connector providers."""
    GOOGLE = "google"
    GOOGLE_DRIVE = "google_drive"
    GITHUB = "github"
    TELEGRAM = "telegram"
    BROWSER = "browser"
    LOCAL_PC = "local_pc"
    WINDOWS_SIDECAR = "windows_sidecar"
    EMAIL = "email"
    REDIS = "redis"
    CUSTOM_MCP = "custom_mcp"
    REST_SERVICE = "rest_service"


class AuthType(str, Enum):
    """Authentication mechanisms for connectors."""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT_BEARER = "jwt_bearer"
    SERVICE_ACCOUNT = "service_account"
    OUTBOUND_TOKEN = "outbound_token"


class ConnectorStatus(str, Enum):
    """Health and connection status of external integration."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    AUTH_REQUIRED = "auth_required"
    ERROR = "error"
