"""
GOOGLE CALENDAR PERMANENT SYNC ENGINE FOR JARVIS & MUKIL
tools/google_calendar_tool.py

Enforces zero-touch multi-device reminder synchronization:
- Synchronizes reminders, milestones, birthdays, and SGC payment dues directly to Google Calendar.
- Alerts Mukil on Android Phone, WearOS Smartwatch, and PC Desktop.
- Includes multi-tier reminder popups: 1 day before, 1 hour before, and 10 minutes before.
- Permanent OAuth refresh token ensures 24/7 autonomous sync without re-login.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google_calendar_tool")

# Standard Indian Standard Time (IST) Timezone
IST = timezone(timedelta(hours=5, minutes=30))

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events"
]

BASE_DIR = Path(__file__).resolve().parent.parent
VAULT_DIR = BASE_DIR / "storage" / "vault"
TOKEN_FILE = VAULT_DIR / "google_calendar_token.json"
CLIENT_SECRET_FILE = VAULT_DIR / "temp_client_secret.json"

def get_calendar_service():
    """
    Retrieves an authorized Google Calendar v3 service instance.
    Auto-refreshes token using permanent refresh_token if expired.
    """
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            logger.warning(f"Error loading {TOKEN_FILE}: {e}")

    # Check fallback token file if available
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("[Google Calendar] Refreshing expired access token...")
                creds.refresh(Request())
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            except Exception as refresh_err:
                logger.warning(f"[Google Calendar] Token refresh failed: {refresh_err}")
                creds = None

    if not creds or not creds.valid:
        logger.error("[Google Calendar] Valid token not found. Authorization required via setup_calendar_oauth.py.")
        return None

    return build("calendar", "v3", credentials=creds)


def add_calendar_reminder(
    title: str,
    start_time_iso: str,
    description: str = "Created autonomously by JARVIS Personal AI Agent",
    duration_minutes: int = 30
) -> Dict[str, Any]:
    """
    Creates an event with multi-tier notification popups on Mukil's Google Calendar.

    Args:
        title: Event title (e.g. 'Ram Birthday 🎂', 'Pay Lakshmi Chemicals Rs 25,000')
        start_time_iso: ISO format datetime string 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SS'
        description: Details or notes
        duration_minutes: Event duration in minutes (default: 30 mins)

    Returns:
        Dict with status, event_id, and html_link
    """
    service = get_calendar_service()
    if not service:
        return {
            "success": False,
            "error": "Google Calendar API not authorized yet. Run setup_calendar_oauth.py to generate permanent token."
        }

    try:
        # Parse start datetime
        clean_time = start_time_iso.replace("T", " ")
        if len(clean_time) == 10:  # YYYY-MM-DD
            dt_start = datetime.strptime(clean_time, "%Y-%m-%d").replace(hour=9, minute=0, second=0, tzinfo=IST)
        elif len(clean_time) == 19:
            dt_start = datetime.strptime(clean_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        else:
            from dateutil import parser
            dt_start = parser.parse(start_time_iso)
            if not dt_start.tzinfo:
                dt_start = dt_start.replace(tzinfo=IST)

        dt_end = dt_start + timedelta(minutes=duration_minutes)

        event_body = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": dt_start.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": dt_end.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 1440},  # 1 day before
                    {"method": "popup", "minutes": 60},    # 1 hour before
                    {"method": "popup", "minutes": 10},    # 10 minutes before
                ],
            },
        }

        created_event = service.events().insert(calendarId="primary", body=event_body).execute()
        event_link = created_event.get("htmlLink", "")
        event_id = created_event.get("id", "")

        logger.info(f"✅ [Google Calendar] Event created: '{title}' ({event_id})")
        return {
            "success": True,
            "event_id": event_id,
            "title": title,
            "scheduled_time": dt_start.strftime("%d-%b-%Y %I:%M %p IST"),
            "html_link": event_link,
            "message": f"Event '{title}' scheduled on Google Calendar for {dt_start.strftime('%d-%b-%Y %I:%M %p IST')}."
        }
    except Exception as e:
        logger.error(f"[Google Calendar Error] Failed to create event: {e}")
        return {"success": False, "error": str(e)}


def list_upcoming_events(max_results: int = 5) -> List[Dict[str, Any]]:
    """Fetches upcoming events from Mukil's primary Google Calendar."""
    service = get_calendar_service()
    if not service:
        return []

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        items = events_result.get("items", [])
        results = []
        for e in items:
            start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date"))
            results.append({
                "id": e.get("id"),
                "summary": e.get("summary", "Untitled"),
                "start": start,
                "link": e.get("htmlLink")
            })
        return results
    except Exception as e:
        logger.error(f"[Google Calendar Error] Failed to list events: {e}")
        return []


if __name__ == "__main__":
    print("=" * 60)
    print("🗓️ GOOGLE CALENDAR TOOL STATUS CHECK")
    print("=" * 60)
    srv = get_calendar_service()
    if srv:
        print("✅ Google Calendar API Service is ACTIVE and CONNECTED!")
        events = list_upcoming_events(3)
        print(f"Upcoming Events ({len(events)}):")
        for ev in events:
            print(f" - {ev['summary']} at {ev['start']}")
    else:
        print("❌ Token not initialized or expired. Run setup_calendar_oauth.py.")
