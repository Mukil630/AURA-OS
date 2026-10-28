"""
AURA OS Telegram Dispatch & Gateway Tools
Enables autonomous dispatch of alerts, bills, documents, photos, and voice notes
directly to Mukil's authenticated Telegram account (@mukil_jarvis_executive_bot).
"""
import os
import time
import requests
from pathlib import Path
from aura.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Cooldown cache to prevent spamming duplicate messages/documents
_DISPATCH_CACHE = {}

def _check_and_update_cache(key: str, cooldown_seconds: int = 60) -> bool:
    """Returns True if duplicate dispatch within cooldown window."""
    now = time.time()
    last_time = _DISPATCH_CACHE.get(key, 0)
    if now - last_time < cooldown_seconds:
        return True
    _DISPATCH_CACHE[key] = now
    return False

def send_telegram_alert(message: str) -> str:
    """
    Sends an instant message or notification directly to Mukil's Telegram phone.
    Args:
        message: The text or markdown message to send.
    """
    if not TELEGRAM_BOT_TOKEN:
        return "❌ Error: TELEGRAM_BOT_TOKEN is not configured in .env."

    # Prevent spamming exact same alert
    if _check_and_update_cache(message.strip()):
        return "⚠️ Notice: This exact alert was already dispatched to Mukil's Telegram within the last 60 seconds. Skipping duplicate."

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(url, json=payload, timeout=25)
        res_json = resp.json()
        if res_json.get("ok"):
            return f"✅ **Successfully dispatched to Boss Mukil's Telegram!** (Chat ID: {TELEGRAM_CHAT_ID})"
        else:
            # Fallback without markdown if markdown parsing failed
            payload.pop("parse_mode", None)
            resp2 = requests.post(url, json=payload, timeout=25)
            if resp2.json().get("ok"):
                return f"✅ **Dispatched to Telegram (Plain Text)!**"
            return f"❌ Telegram API Error: {res_json.get('description')}"
    except Exception as e:
        return f"❌ Failed to dispatch to Telegram: {str(e)}"


def send_telegram_document(file_path_or_url: str, caption: str = "") -> str:
    """
    Sends a document, PDF invoice, image, or Google Drive link directly to Mukil's Telegram.
    Args:
        file_path_or_url: The local file path (PDF/image) or web/Google Drive URL to send.
        caption: Optional caption to accompany the file.
    """
    if not TELEGRAM_BOT_TOKEN:
        return "❌ Error: TELEGRAM_BOT_TOKEN is not configured in .env."

    # If it is a web link / Google Drive link
    if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
        text = f"📄 **Document / Invoice Link for Boss Mukil:**\n\n🔗 {file_path_or_url}"
        if caption:
            text += f"\n\n📝 **Note:** {caption}"
        return send_telegram_alert(text)

    # Local file path
    p = Path(file_path_or_url)
    if not p.exists():
        return f"❌ Error: File not found on disk at '{file_path_or_url}'."

    if _check_and_update_cache(str(p.resolve())):
        return f"⚠️ Notice: '{p.name}' was already sent to Mukil's Telegram within the last 60 seconds. Skipping duplicate."

    suffix = p.suffix.lower()
    endpoint = "sendPhoto" if suffix in [".png", ".jpg", ".jpeg"] else "sendDocument"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{endpoint}"

    try:
        with open(p, "rb") as f:
            field_name = "photo" if endpoint == "sendPhoto" else "document"
            files = {field_name: f}
            data = {"chat_id": TELEGRAM_CHAT_ID}
            if caption:
                data["caption"] = caption
            resp = requests.post(url, data=data, files=files, timeout=30)
            res_json = resp.json()
            if res_json.get("ok"):
                return f"✅ **File '{p.name}' successfully sent to Mukil's Telegram!**"
            return f"❌ Telegram API Error: {res_json.get('description')}"
    except Exception as e:
        return f"❌ Failed to upload file to Telegram: {str(e)}"
