import os
import sys
import json
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DRIVE_FOLDER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drive_sync")

SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "vault")
TOKEN_FILE = os.path.join(VAULT_DIR, "google_drive_token.json")

def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check sgc-billing client secret
            appdata_p = os.path.join(os.environ.get('APPDATA', ''), 'sgc-billing', 'sgc-billing-data.json')
            client_secret_data = None
            if os.path.exists(appdata_p):
                try:
                    with open(appdata_p, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        client_secret_data = d.get('google-client-secret')
                except Exception:
                    pass

            if not client_secret_data:
                logger.error("No Google Client Secret found.")
                return None

            temp_secret_file = os.path.join(VAULT_DIR, "temp_client_secret.json")
            with open(temp_secret_file, 'w', encoding='utf-8') as f:
                json.dump(client_secret_data, f)

            flow = InstalledAppFlow.from_client_secrets_file(temp_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

            if os.path.exists(temp_secret_file):
                os.remove(temp_secret_file)

        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def upload_file_to_vault(service, file_path, folder_id=DRIVE_FOLDER_ID):
    if not os.path.exists(file_path):
        return None
    file_name = os.path.basename(file_path)
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    logger.info(f"✅ Uploaded '{file_name}' to Google Drive Master Vault! Link: {file.get('webViewLink')}")
    return file

def sync_all_memory_to_drive():
    service = get_drive_service()
    if not service:
        print("Drive service not available.")
        return

    base_dir = os.path.dirname(os.path.dirname(__file__))
    files_to_sync = [
        os.path.join(base_dir, "storage", "memory", "user_profile.json"),
        os.path.join(base_dir, "storage", "memory", "context.json"),
        os.path.join(base_dir, "storage", "memory", "system_blueprint.json"),
        os.path.join(base_dir, "README.md"),
        os.path.join(base_dir, "AURA_LIVE_PRACTICAL_PROOF.txt"),
        r"C:\Users\mukil\OneDrive\placement questions\MK.PDF.RESUME.pdf"
    ]

    print(f"\n🚀 Syncing files to 5TB Google Drive Master Vault ({DRIVE_FOLDER_ID})...")
    for f in files_to_sync:
        if os.path.exists(f):
            upload_file_to_vault(service, f, DRIVE_FOLDER_ID)

    print("\n🎉 Google Drive 5TB Vault Sync Complete! Check your folder online.")

if __name__ == "__main__":
    sync_all_memory_to_drive()
