"""1-Click Google OAuth 2.0 Setup Script for AURA-OS (Gmail, Calendar, Drive).
Run this after placing your downloaded 'credentials.json' in this folder.
"""
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.file",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def setup_oauth():
    print("=" * 60)
    print("🌌 AURA-OS Google OAuth 2.0 Authenticator")
    print("=" * 60)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ ERROR: '{CREDENTIALS_FILE}' not found!")
        print("👉 Please download your OAuth Client credentials from Google Cloud Console,")
        print(f"   rename it to 'credentials.json', and place it in: {BASE_DIR}")
        sys.exit(1)

    print("🔑 Found credentials.json! Launching browser for 1-click authorization...")
    
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Save permanent token.json
    with open(TOKEN_FILE, "w", encoding="utf-8") as token_out:
        token_out.write(creds.to_json())

    print(f"✅ SUCCESS! OAuth token generated and saved to: {TOKEN_FILE}")
    
    # Test connection
    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email_addr = profile.get("emailAddress", "Unknown")
        print(f"🎉 Connected to Gmail Account: {email_addr}")
        print("🚀 AURA 24/7 Interview Radar & Calendar Sync are now 100% operational!")
    except Exception as e:
        print(f"⚠️ Warning during test verification: {e}")


if __name__ == "__main__":
    setup_oauth()
