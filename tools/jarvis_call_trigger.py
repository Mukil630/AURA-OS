"""
JARVIS Autonomous Phone Call Trigger
Part of Mapla's Strategy Room - Master Blueprint Implementation
Supports:
1. Method A: MacroDroid HTTP Webhook Trigger (Spare Android Phone with SIM) -> Zero Cost
2. Method C: Twilio Voice Call API -> Direct Cellular Call
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "memory", "context.json")

def trigger_macrodroid_call(webhook_url: str):
    """
    Sends an HTTP GET request to MacroDroid Webhook.
    MacroDroid triggers: Action -> Make Call -> Mukil's Primary Mobile Number.
    """
    print(f"[JARVIS CALL] Pinging MacroDroid Webhook: {webhook_url}")
    try:
        req = urllib.request.Request(
            webhook_url,
            headers={"User-Agent": "JARVIS-Prime/2.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            print(f"[JARVIS CALL] MacroDroid Response: HTTP {status_code} - Trigger dispatched successfully!")
            return True
    except urllib.error.URLError as e:
        print(f"[JARVIS CALL ERROR] Failed to ping MacroDroid webhook: {e}")
        return False

def trigger_twilio_call(account_sid: str, auth_token: str, from_number: str, to_number: str, voice_message: str):
    """
    Triggers an automated voice call via Twilio API.
    Plays speech synthesis upon answering.
    """
    try:
        from twilio.rest import Client
    except ImportError:
        print("[JARVIS CALL] Twilio library not found. Install via: pip install twilio")
        return False

    try:
        client = Client(account_sid, auth_token)
        twiml_payload = f"<Response><Say voice='Polly.Aditi'>{voice_message}</Say></Response>"
        call = client.calls.create(
            twiml=twiml_payload,
            to=to_number,
            from_=from_number
        )
        print(f"[JARVIS CALL] Twilio Call initiated! Call SID: {call.sid}")
        return True
    except Exception as e:
        print(f"[JARVIS CALL ERROR] Twilio call failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="JARVIS Autonomous Phone Call Initiator")
    parser.add_argument("--method", choices=["macrodroid", "twilio"], default="macrodroid", help="Call trigger method")
    parser.add_argument("--webhook", type=str, help="MacroDroid Webhook URL (for Method A)")
    parser.add_argument("--to", type=str, default="+918072044874", help="Recipient phone number")
    parser.add_argument("--message", type=str, default="Boss, this is JARVIS. System update complete.", help="Voice message for Twilio call")

    args = parser.parse_args()

    if args.method == "macrodroid":
        if not args.webhook:
            print("[JARVIS CALL] Note: Provide --webhook '<your_macrodroid_webhook_url>'")
            print("Setup Steps for Method A:")
            print("1. Install MacroDroid on spare phone with SIM.")
            print("2. Add Macro -> Trigger: Webhook (gives you a URL like https://trigger.macrodroid.com/...)")
            print("3. Action: Make Call -> Mukil's Mobile Number.")
            return
        trigger_macrodroid_call(args.webhook)

    elif args.method == "twilio":
        sid = os.environ.get("TWILIO_ACCOUNT_SID")
        token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_num = os.environ.get("TWILIO_FROM_NUMBER")
        if not (sid and token and from_num):
            print("[JARVIS CALL] Twilio credentials missing in environment variables.")
            print("Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER.")
            return
        trigger_twilio_call(sid, token, from_num, args.to, args.message)

if __name__ == "__main__":
    main()
