import os
from dotenv import load_dotenv

# Load from .env in project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8765"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

DEFAULT_TAMIL_VOICE = os.getenv("DEFAULT_TAMIL_VOICE", "ta-IN-ValluvarNeural")
DEFAULT_ENGLISH_VOICE = os.getenv("DEFAULT_ENGLISH_VOICE", "en-IN-PrabhatNeural")

USER_NAME = os.getenv("USER_NAME", "Mukil")
AGENT_NAME = os.getenv("AGENT_NAME", "JARVIS Prime")
