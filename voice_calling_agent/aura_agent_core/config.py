import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Load credentials from .env in current or root path
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(".env")

# Turso Cloud Database Configuration (AWS Mumbai - Free 5 GB Tier)
DEFAULT_TURSO_URL = "libsql://aura-db-mukil.aws-ap-south-1.turso.io"
DEFAULT_TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTE3OTQzNDYsImlkIjoiMDFhMTJmNDAtYmYwMS03NTViLThmZjUtYTNhZDE3NzNiMDMxIiwia2lkIjoiZldreldSYjdtbjdCaURZRFMwVXA3Zl9RbmhwT1kwZnRwWVh4akJ3eEVnMCIsInJpZCI6ImJlMzFlYjI4LWJiOWQtNDJlMS04NGZjLWRiY2E0N2NlMmFjOCJ9.o8EDMt1k_W5sv1MrH0_Ac_gfyR_8Io4Z0Omy7OmDxxiCW629nbR7v3gpiEkhF4_SQkhhvqb0o1s2O8kynPgwCw"

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", DEFAULT_TURSO_URL).replace("libsql://", "https://")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", DEFAULT_TURSO_TOKEN)

# Standard Indian Standard Time (IST) Timezone
IST = timezone(timedelta(hours=5, minutes=30))

# Daemon settings
POLL_INTERVAL_SECONDS = 15
