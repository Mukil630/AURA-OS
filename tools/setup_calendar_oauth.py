"""
1-CLICK GOOGLE CALENDAR & DRIVE OAUTH AUTHENTICATOR (STANDARD CLEAN FLOW)
tools/setup_calendar_oauth.py

Generates permanent refresh token for Google Calendar & Drive API.
Saves token to storage/vault/google_calendar_token.json.
Uses standard flow.run_local_server(port=0) to guarantee zero state or PKCE mismatches.
"""

import os
import sys
import json
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent.parent
VAULT_DIR = BASE_DIR / "storage" / "vault"
TOKEN_FILE = VAULT_DIR / "google_calendar_token.json"
CLIENT_SECRET_FILE = VAULT_DIR / "temp_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def main():
    print("=" * 65, flush=True)
    print("🗓️  JARVIS GOOGLE CALENDAR & DRIVE OAUTH 2.0 INITIALIZER", flush=True)
    print("=" * 65, flush=True)

    if not CLIENT_SECRET_FILE.exists():
        print(f"❌ Error: Client secret file missing at {CLIENT_SECRET_FILE}", flush=True)
        return

    with open(CLIENT_SECRET_FILE, "r", encoding="utf-8") as f:
        client_config = json.load(f)

    target_key = "installed" if "installed" in client_config else "web"
    client_config[target_key]["auth_uri"] = "https://accounts.google.com/o/oauth2/auth"
    client_config[target_key]["token_uri"] = "https://oauth2.googleapis.com/token"

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    print("👉 Opening your default browser for 1-click Google Authorization...", flush=True)
    print("   Please select mukilarasu55@gmail.com and click 'Allow'!", flush=True)
    print("=" * 65, flush=True)

    # Standard native local server on dynamic open port (guarantees matching state and PKCE verifier)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    token_json = creds.to_json()
    with open(TOKEN_FILE, "w", encoding="utf-8") as out:
        out.write(token_json)

    # Sync to voice calling agent storage folders
    repo_vault = Path("C:/Users/mukil/jarvis-voice-calling-agent-repo/storage/vault")
    repo_vault.mkdir(parents=True, exist_ok=True)
    with open(repo_vault / "google_calendar_token.json", "w", encoding="utf-8") as out:
        out.write(token_json)

    cont_vault = Path("C:/Users/mukil/continuous-calling-agent/storage/vault")
    cont_vault.mkdir(parents=True, exist_ok=True)
    with open(cont_vault / "google_calendar_token.json", "w", encoding="utf-8") as out:
        out.write(token_json)

    print("\n" + "=" * 65, flush=True)
    print("✅ PERMANENT GOOGLE CALENDAR OAUTH TOKEN SAVED SUCCESSFULLY!", flush=True)
    print(f"📁 Path: {TOKEN_FILE}", flush=True)
    print("=" * 65, flush=True)

    # Verification Test: Create live event
    try:
        service = build("calendar", "v3", credentials=creds)
        test_event = {
            "summary": "Ram Birthday 🎂",
            "description": "Automated reminder synced via JARVIS Personal AI Agent",
            "start": {
                "dateTime": "2026-10-25T09:00:00+05:30",
                "timeZone": "Asia/Kolkata"
            },
            "end": {
                "dateTime": "2026-10-25T09:30:00+05:30",
                "timeZone": "Asia/Kolkata"
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 1440},
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 10}
                ]
            }
        }
        res = service.events().insert(calendarId="primary", body=test_event).execute()
        print(f"🚀 Live Test Event Created: 'Ram Birthday 🎂' on 25-Oct-2026 09:00 AM IST!", flush=True)
        print(f"🔗 View in Google Calendar: {res.get('htmlLink')}", flush=True)
        print("=" * 65, flush=True)
    except Exception as e:
        print(f"Notice during verification: {e}", flush=True)

if __name__ == "__main__":
    main()
