"""
Universal Cloud Sheet Hub for AURA OS
Enforces Cloud-First architecture: Any Excel or CSV created is automatically uploaded 
to Mukil's Google Drive Master Vault as a native live Google Spreadsheet.
"""
import os
import sys
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cloud_sheet_hub")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, "storage", "vault", "google_drive_token.json")
MASTER_VAULT_FOLDER_ID = "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ"
SERVICE_ACCOUNT_EMAIL = "sgc-drive-bot@sgc-billing.iam.gserviceaccount.com"


def upload_excel_to_google_sheet(
    local_file_path: str,
    title: Optional[str] = None,
    folder_id: str = MASTER_VAULT_FOLDER_ID
) -> Dict[str, Any]:
    """
    Uploads any local Excel or CSV file to Google Drive and converts it to a live Google Sheet.
    Grants edit permissions to the SGC Service Account.
    Returns the live Google Sheet link.
    """
    if not os.path.exists(local_file_path):
        return {"status": "error", "message": f"Local file not found: {local_file_path}"}

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        drive = build("drive", "v3", credentials=creds)

        file_name = title or os.path.splitext(os.path.basename(local_file_path))[0].replace("_", " ")

        file_metadata = {
            "name": file_name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id]
        }

        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if local_file_path.endswith(".csv"):
            mimetype = "text/csv"

        media = MediaFileUpload(local_file_path, mimetype=mimetype, resumable=True)

        created_file = drive.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink"
        ).execute()

        file_id = created_file.get("id")
        live_link = created_file.get("webViewLink")

        # Grant writer permissions to service account
        try:
            perm = {"type": "user", "role": "writer", "emailAddress": SERVICE_ACCOUNT_EMAIL}
            drive.permissions().create(fileId=file_id, body=perm, fields="id").execute()
        except Exception as pe:
            logger.warning(f"Service account permission notice: {pe}")

        logger.info(f"Uploaded Google Sheet successfully: {file_name} -> {live_link}")
        return {
            "status": "success",
            "file_id": file_id,
            "title": file_name,
            "live_url": live_link
        }
    except Exception as e:
        logger.error(f"Failed to upload Google Sheet: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        res = upload_excel_to_google_sheet(sys.argv[1])
        print("Upload Result:", res)
