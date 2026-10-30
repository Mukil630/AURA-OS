"""
Universal Cloud Sheet Hub for AURA OS
Enforces Cloud-First architecture: Any Excel or CSV created is automatically uploaded 
to Mukil's Google Drive Master Vault as a native live Google Spreadsheet.
"""
import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cloud_sheet_hub")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, "storage", "vault", "google_drive_token.json")
REGISTRY_PATH = os.path.join(BASE_DIR, "storage", "memory", "cloud_sheets_registry.json")
MASTER_VAULT_FOLDER_ID = "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ"
SERVICE_ACCOUNT_EMAIL = "sgc-drive-bot@sgc-billing.iam.gserviceaccount.com"


def get_all_registered_sheets() -> List[Dict[str, Any]]:
    """Loads all registered cloud sheets from persistent registry."""
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read sheets registry: {e}")
    return []


def register_sheet_in_hub(
    file_id: str,
    title: str,
    url: str,
    category: str = "Business",
    description: str = ""
) -> None:
    """Registers a new or existing sheet in the persistent hub registry."""
    sheets = get_all_registered_sheets()
    for s in sheets:
        if s.get("id") == file_id:
            s["title"] = title
            s["url"] = url
            s["category"] = category
            if description:
                s["description"] = description
            break
    else:
        sheets.append({
            "id": file_id,
            "title": title,
            "category": category,
            "url": url,
            "description": description or f"Cloud Google Sheet: {title}",
            "created_at": datetime.now().isoformat()
        })

    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(sheets, f, indent=2)
    logger.info(f"Registered sheet in hub: {title} ({file_id})")


def format_sheets_hub_message() -> str:
    """Formats all active Google Sheets into a clean Telegram message with 1-click links."""
    sheets = get_all_registered_sheets()
    if not sheets:
        return "📱 Mukil's Cloud Sheet Hub: No active sheets registered yet."

    lines = ["📱 *Mukil's Master Google Sheets Cloud Hub*:\n"]
    for idx, s in enumerate(sheets, start=1):
        icon = "💰" if "Budget" in s.get("title", "") or "Finance" in s.get("category", "") else "🏭"
        lines.append(f"{idx}. {icon} *{s.get('title')}*")
        lines.append(f"   📂 Category: {s.get('category')}")
        lines.append(f"   🔗 [Open Live Sheet]({s.get('url')})\n")

    lines.append("💡 *Agent Direct Directives*:")
    lines.append("• Production log: `record bleaching 1500 kg for Sowbhagiya at 12 rs`")
    lines.append("• Daily expense: `chemical H2O2 4500 rs Lakshmi Chemicals`")
    lines.append("• Pull live edits from phone: `sheet check panni update pannu`")
    return "\n".join(lines)


def upload_excel_to_google_sheet(
    local_file_path: str,
    title: Optional[str] = None,
    category: str = "Business",
    description: str = "",
    folder_id: str = MASTER_VAULT_FOLDER_ID
) -> Dict[str, Any]:
    """
    Uploads any local Excel or CSV file to Google Drive and converts it to a live Google Sheet.
    Grants edit permissions to the SGC Service Account.
    Registers in the cloud sheets hub.
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

        register_sheet_in_hub(file_id, file_name, live_link, category, description)

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
    print(format_sheets_hub_message())
