"""
AURA OS Config - Environment and Settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "6233907249"))

# Turso Cloud Database (AWS Mumbai - Free 5 GB Tier)
DEFAULT_TURSO_URL = "libsql://aura-db-mukil.aws-ap-south-1.turso.io"
DEFAULT_TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTE3OTQzNDYsImlkIjoiMDFhMTJmNDAtYmYwMS03NTViLThmZjUtYTNhZDE3NzNiMDMxIiwia2lkIjoiZldreldSYjdtbjdCaURZRFMwVXA3Zl9RbmhwT1kwZnRwWVh4akJ3eEVnMCIsInJpZCI6ImJlMzFlYjI4LWJiOWQtNDJlMS04NGZjLWRiY2E0N2NlMmFjOCJ9.o8EDMt1k_W5sv1MrH0_Ac_gfyR_8Io4Z0Omy7OmDxxiCW629nbR7v3gpiEkhF4_SQkhhvqb0o1s2O8kynPgwCw"
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", DEFAULT_TURSO_URL).replace("libsql://", "https://")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", DEFAULT_TURSO_TOKEN)

# Model selection - Default to ultra-fast Gemini 3.5 Flash Lite
DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "openai/gpt-oss-120b"
]
DEFAULT_ENGINE = os.getenv("DEFAULT_ENGINE", "gemini")  # Options: 'gemini', 'groq', 'dual'

# User context
USER_NAME = "Mukil"
USER_ROLE = "AI Engineer & Entrepreneur"
AGENT_NAME = "AURA"
AGENT_DYNAMIC = "JARVIS Prime / Mapla"

# Workspaces
WORKSPACE_DIR = Path("C:/Users/mukil")
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
