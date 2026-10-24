"""
Test Voice Intent Gatekeeper & Staging Buffer
Demonstrates:
1. Tanglish Input Parsing
2. Staging Buffer (NO blind saving)
3. Disambiguation / Clarification Question Generation
4. Atomic Commit only after Mukil's approval
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import json
import re
from datetime import datetime, timedelta

def parse_tanglish_voice_intent(voice_transcript: str):
    """
    Parses Tanglish voice note into candidate entities.
    Does NOT save to database!
    """
    transcript = voice_transcript.lower()
    
    # Simple regex / heuristic extractor for demo test
    amount_match = re.search(r'₹?\s*(\d+[kK]|\d+,\d+|\d+)', transcript)
    amount = None
    if amount_match:
        raw_amt = amount_match.group(1).lower().replace(',', '')
        if 'k' in raw_amt:
            amount = int(float(raw_amt.replace('k', '')) * 1000)
        else:
            amount = int(raw_amt)
            
    # Entity Mill detection
    mill_match = None
    known_mills = ["bannari", "sowbhagiya", "gaia", "priya", "lakshmi", "shri ram", "kpr"]
    for m in known_mills:
        if m in transcript:
            mill_match = m.title()
            break
            
    # Date detection (Monday, tomorrow, etc.)
    target_date = None
    today = datetime.now()
    if "monday" in transcript:
        days_ahead = 7 - today.weekday() if today.weekday() != 0 else 7
        target_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    elif "tomorrow" in transcript or "naalaiki" in transcript:
        target_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    is_actionable = bool(mill_match or amount or "payment" in transcript or "remind" in transcript)
    
    staging_buffer = {
        "status": "STAGED_AWAITING_CONFIRMATION",
        "raw_text": voice_transcript,
        "is_actionable": is_actionable,
        "entities": {
            "customer_mill": mill_match or "Unknown Mill",
            "amount": amount,
            "target_date": target_date,
            "category": "SGC_PAYMENT_FOLLOWUP" if amount else "GENERAL_TASK"
        }
    }
    return staging_buffer

def generate_clarification_prompt(staged_data: dict) -> str:
    """Generates punchy 1-2 line Tanglish question for Mukil before saving."""
    ent = staged_data["entities"]
    mill = ent["customer_mill"]
    amt = f"₹{ent['amount']:,}" if ent["amount"] else "amount not specified"
    dt = ent["target_date"] or "upcoming date"
    
    return f"Mapla, '{mill}' kitta irundhu {amt} ({dt}) follow-up nu draft pannirukken. Idhai Turso-la reminder-ah lock pannava, illa direct entry podava?"

# Test Run
sample_voice = "Mapla note panniko, Bannari mill Monday ₹30k payment tharom-nu sonnanga."
staged = parse_tanglish_voice_intent(sample_voice)
clarification = generate_clarification_prompt(staged)

print("="*60)
print("1. INCOMING VOICE:", sample_voice)
print("2. STAGED BUFFER (NOT SAVED IN DB YET):")
print(json.dumps(staged, indent=2))
print("3. CLARIFICATION QUESTION TO MUKIL:")
print(clarification)
print("="*60)
