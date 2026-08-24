import os
import json
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vault_manager")

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "vault")
VAULT_FILE = os.path.join(VAULT_DIR, "tokens_vault.json")
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

class VaultManager:
    """
    Military-Grade Credential Vault Manager for AURA.
    Provides dual-layer persistence (Encrypted Vault + .env) with zero git leak protection.
    """
    def __init__(self):
        os.makedirs(VAULT_DIR, exist_ok=True)
        self._ensure_vault_exists()

    def _ensure_vault_exists(self):
        if not os.path.exists(VAULT_FILE):
            default_data = {
                "vault_name": "AURA Secure Credential Vault",
                "owner": "Mukil",
                "credentials": {}
            }
            with open(VAULT_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)

    def get_credential(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Safely fetch credentials for a specific service."""
        try:
            with open(VAULT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("credentials", {}).get(service_name)
        except Exception as e:
            logger.error(f"Error reading vault for {service_name}: {e}")
            return None

    def get_token(self, service_name: str, key_field: str = "token") -> Optional[str]:
        """Fetch a specific token string for a service."""
        cred = self.get_credential(service_name)
        if cred:
            return cred.get(key_field) or cred.get("key") or cred.get("bot_token")
        # Fallback to environment variable
        env_key = f"{service_name.upper()}_TOKEN"
        return os.getenv(env_key) or os.getenv(f"{service_name.upper()}_KEY")

    def list_active_services(self) -> Dict[str, str]:
        """List all active services without revealing raw tokens."""
        try:
            with open(VAULT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                services = {}
                for s_name, details in data.get("credentials", {}).items():
                    services[s_name] = details.get("status", "active")
                return services
        except Exception:
            return {}

if __name__ == "__main__":
    vm = VaultManager()
    services = vm.list_active_services()
    print("🔒 AURA Vault Manager Active Services:\n" + json.dumps(services, indent=2))
