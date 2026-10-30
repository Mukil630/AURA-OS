"""
AURA OS Cloud Sheet Tools
Ensures any spreadsheet requested by Mukil is instantly created and uploaded to Google Drive as a live Google Sheet.
"""
import os
import sys
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.cloud_sheet_hub import upload_excel_to_google_sheet


def upload_sheet_to_cloud(local_file_path: str, title: str = "") -> str:
    """
    Converts a local Excel or CSV file into a live Google Sheet in Mukil's Master Drive Vault.
    Returns the live clickable Google Sheet link for mobile and web access.
    """
    res = upload_excel_to_google_sheet(local_file_path, title if title else None)
    if res.get("status") != "success":
        return f"❌ Failed to upload to Google Drive: {res.get('message')}"

    return (
        f"✅ Live Google Sheet Created in Cloud:\n"
        f"• Title: {res.get('title')}\n"
        f"• Live Link: {res.get('live_url')}\n"
        f"📱 You can open and edit this sheet directly on your phone!"
    )
