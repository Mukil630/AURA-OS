"""
AURA BULLETPROOF VOICE INTENT GATEKEEPER & STAGING BUFFER (v2 PRODUCTION)
File: aura_agent_core/voice_intent_gatekeeper.py

Handles:
1. SGC Business Financials (Mills, Amounts in ₹, k, aayiram, lakh, dates)
2. MNC Placement & Career (Interviews, Tests, Resumes, Portals)
3. Personal & Family Errands (Bills, Rent, Appointments, Birthdays)
4. Ambiguous / Missing-Param Detection (Targeted Clarification Prompts)
5. Pure Casual Chatter / Rants Filter (ZERO Staging, ZERO DB Writes)
6. Atomic Confirmation / Discard Cycle
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from aura_agent_core.nlp_parser import parse_natural_time
from aura_agent_core.services import create_reminder, save_to_vault

STAGING_BUFFER: Dict[str, Dict[str, Any]] = {}

# Entity Dictionaries
KNOWN_MILLS = [
    "bannari", "bannari amman", "sowbhagiya", "gaia", "priya", 
    "lakshmi", "shri ram", "kpr", "aravind", "sundar", "amarjothi"
]

COMPANIES = [
    "infinite", "infinite computer solutions", "tcs", "zoho", "amazon", 
    "accenture", "cognizant", "infosys", "wipro", "hcl", "leetcode"
]

CASUAL_INDICATORS = [
    "weather", "hot-ah", "rain", "bore", "pasikidhu", "biryani", "tea", 
    "padam", "movie", "kgf", "match", "traffic", "tired", "thoonga", "chumma"
]

def parse_amount(text: str) -> Optional[int]:
    """Extracts currency values in ₹, k, aayiram, lakh, comma-separated."""
    text_lower = text.lower()
    
    # Check for Lakh
    lakh_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lacs|patcham)', text_lower)
    if lakh_match:
        return int(float(lakh_match.group(1)) * 100000)
        
    # Check for Aayiram (Tamil thousand)
    aayiram_match = re.search(r'(\d+)\s*(?:aayiram|ayiram)', text_lower)
    if aayiram_match:
        return int(aayiram_match.group(1)) * 1000

    # Check standard ₹ / numbers with k or commas (Avoid 'kg' fabric weights!)
    amt_match = re.search(r'(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*([kK])?(?!g|G)', text_lower)
    if amt_match:
        raw_val = amt_match.group(1).replace(',', '')
        is_k = bool(amt_match.group(2))
        try:
            val = float(raw_val)
            # Avoid picking up single digits like '5%' or '2 days' as amounts unless ₹ or k present
            if not is_k and '₹' not in text_lower and 'rs' not in text_lower and val < 500:
                return None
            return int(val * 1000) if is_k else int(val)
        except ValueError:
            pass
    return None

def detect_target_date(text: str) -> tuple[Optional[str], str]:
    """Parses date/time entities into ISO format and user-friendly display string."""
    text_lower = text.lower()
    today = datetime.now()
    
    days_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for day_name, day_idx in days_map.items():
        if day_name in text_lower:
            days_ahead = (day_idx - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target_dt = today + timedelta(days=days_ahead)
            return target_dt.strftime("%Y-%m-%d 09:00:00"), f"{day_name.title()} ({target_dt.strftime('%d %b')})"

    for kw in ["naalaiki", "tomorrow"]:
        if kw in text_lower:
            target_dt = today + timedelta(days=1)
            return target_dt.strftime("%Y-%m-%d 09:00:00"), f"Tomorrow ({target_dt.strftime('%d %b')})"
            
    if "tonight" in text_lower or "night" in text_lower:
        return today.strftime("%Y-%m-%d 21:00:00"), "Tonight 9:00 PM"
        
    in_days_match = re.search(r'in\s*(\d+)\s*days?', text_lower)
    if in_days_match:
        num = int(in_days_match.group(1))
        target_dt = today + timedelta(days=num)
        return target_dt.strftime("%Y-%m-%d 09:00:00"), f"In {num} days ({target_dt.strftime('%d %b')})"

    return None, "upcoming date"


def stage_voice_note(voice_transcript: str) -> Dict[str, Any]:
    """
    Main Cognitive Filter:
    - Pure Casual chatter -> REJECT IMMEDIATELY (0 DB write, 0 Staging).
    - Actionable Business / Career / Personal -> Buffer in RAM, generate clarification question.
    - Ambiguous -> Identify missing entity and ask targeted question.
    """
    clean_text = voice_transcript.strip()
    lower_text = clean_text.lower()
    
    # -------------------------------------------------------------------
    # FILTER 1: CASUAL CHATTER / SMALL TALK (ZERO POLLUTION GATEWAY)
    # -------------------------------------------------------------------
    has_casual = any(w in lower_text for w in CASUAL_INDICATORS)
    has_action_intent = any(w in lower_text for w in [
        "payment", "tharom", "balance", "challan", "interview", "deadline", 
        "exam", "test", "resume", "remind", "note", "gpay", "rent", "appointment", 
        "birthday", "fees", "cheque", "discount", "invoice"
    ])
    
    if has_casual and not has_action_intent:
        return {
            "success": True,
            "status": "CASUAL_CHATTER_IGNORED",
            "is_actionable": False,
            "db_written": False,
            "staging_buffer": False,
            "conversational_reply": "Haha crt mapla! Idhai database-la save panna vendam la? Chill-ah irupom! 😎"
        }

    # -------------------------------------------------------------------
    # FILTER 2: ENTITY EXTRACTION
    # -------------------------------------------------------------------
    # Mill Entity
    detected_mill = None
    for m in KNOWN_MILLS:
        if m in lower_text:
            detected_mill = m.title()
            break
            
    # Company / Placement Entity
    detected_company = None
    for c in COMPANIES:
        if c in lower_text:
            detected_company = c.title()
            break
            
    # Financial Amount Entity
    detected_amount = parse_amount(clean_text)
    
    # Date / Time Entity
    target_iso, display_time = detect_target_date(clean_text)

    # -------------------------------------------------------------------
    # FILTER 3: AMBIGUITY DETECTION (MISSING CRITICAL PARAMS)
    # -------------------------------------------------------------------
    is_ambiguous = False
    clarification_msg = ""
    
    # Scenario A: SGC Payment mentioned, but Mill is missing!
    if ("payment" in lower_text or "balance" in lower_text or "collect" in lower_text or "cheque" in lower_text) and not detected_mill and not detected_company:
        is_ambiguous = True
        amt_str = f"₹{detected_amount:,}" if detected_amount else "payment"
        clarification_msg = f"Mapla, {amt_str} collect pannanum-nu sonniye, endha mill kitta irundhu? Mill peru sollunga mapla!"
        category = "AMBIGUOUS_MISSING_MILL"

    # Scenario B: Interview / Exam mentioned, but Company / Role is missing!
    elif ("interview" in lower_text or "test" in lower_text or "drive" in lower_text) and not detected_company:
        is_ambiguous = True
        clarification_msg = "Mapla, interview / test pathi sonniye, endha company / exam name sollu mapla, accurate-ah schedule panren?"
        category = "AMBIGUOUS_MISSING_COMPANY"

    # Scenario C: Amount mentioned with zero context
    elif detected_amount and not detected_mill and not detected_company and not any(k in lower_text for k in ["rent", "fees", "petrol"]):
        is_ambiguous = True
        clarification_msg = f"Mapla, ₹{detected_amount:,} sonniye, idhu SGC mill payment-ah illa personal expense-ah? Context konjam sollu mapla!"
        category = "AMBIGUOUS_MISSING_CONTEXT"

    # -------------------------------------------------------------------
    # FILTER 4: CLEAR ACTIONABLE CATEGORIZATION
    # -------------------------------------------------------------------
    else:
        if detected_mill or (detected_amount and "chemical" in lower_text):
            category = "SGC_PAYMENT_FOLLOWUP"
            amt_str = f"₹{detected_amount:,}" if detected_amount else "amount"
            clarification_msg = f"Mapla, '{detected_mill or 'SGC Mill'}' kitta irundhu {amt_str} ({display_time}) follow-up nu draft pannirukken. Turso-la reminder lock pannava?"
        elif detected_company or any(k in lower_text for k in ["placement", "resume", "aptitude", "interview", "assessment", "exam", "coding", "dsa"]):
            category = "CAREER_PLACEMENT"
            clarification_msg = f"Mapla, '{detected_company or 'Career'}' task: '{clean_text}' ({display_time})-ku lock pannidava?"
        else:
            category = "PERSONAL_REMINDER"
            clarification_msg = f"Mapla, '{clean_text}' ({display_time}) un personal task-la lock pannanuma?"

    # -------------------------------------------------------------------
    # BUFFER CREATION (RAM ONLY - ZERO DB WRITES)
    # -------------------------------------------------------------------
    draft_id = f"STG-{uuid.uuid4().hex[:6].upper()}"
    staged_record = {
        "draft_id": draft_id,
        "status": "STAGED_AWAITING_CONFIRMATION",
        "timestamp": datetime.now().isoformat(),
        "raw_transcript": clean_text,
        "is_ambiguous": is_ambiguous,
        "category": category,
        "entities": {
            "customer_mill": detected_mill,
            "company": detected_company,
            "amount": detected_amount,
            "target_iso": target_iso,
            "display_time": display_time
        }
    }
    STAGING_BUFFER[draft_id] = staged_record

    return {
        "success": True,
        "draft_id": draft_id,
        "status": "STAGED_IN_RAM",
        "is_actionable": True,
        "is_ambiguous": is_ambiguous,
        "category": category,
        "staged_entities": staged_record["entities"],
        "clarification_question": clarification_msg,
        "db_written": False
    }


async def resolve_voice_note(draft_id: str, mukil_decision: str) -> Dict[str, Any]:
    """Commits or drops staged drafts cleanly."""
    if draft_id not in STAGING_BUFFER:
        return {"success": False, "error": f"Draft {draft_id} not found."}
        
    staged = STAGING_BUFFER.pop(draft_id)
    decision = mukil_decision.lower().strip()
    
    approval_tokens = ["aama", "yes", "lock", "save", "reminder", "podu", "ok", "confirm", "pannu", "schedule"]
    rejection_tokens = ["vendaam", "cancel", "no", "chumma", "leave", "drop", "beda", "vidu"]
    
    is_approved = any(token in decision for token in approval_tokens)
    is_rejected = any(token in decision for token in rejection_tokens)
    
    if is_approved and not is_rejected:
        ent = staged["entities"]
        if ent["customer_mill"]:
            amt_str = f" - ₹{ent['amount']:,}" if ent['amount'] else ""
            title = f"SGC Followup: {ent['customer_mill']}{amt_str}"
        elif ent["company"]:
            title = f"Placement: {ent['company']} - {staged['raw_transcript']}"
        else:
            title = staged["raw_transcript"]

        target_iso = ent["target_iso"] or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 09:00:00")
        rem_id = await create_reminder(title, target_iso)
        
        return {
            "success": True,
            "action": "COMMITTED_TO_TURSO_CLOUD",
            "task_id": rem_id,
            "title": title,
            "scheduled_at": target_iso,
            "speech_reply": f"Done mapla! '{title}' Turso Cloud-la #{rem_id} ah lock panniten!"
        }
    else:
        return {
            "success": True,
            "action": "DISCARDED_ZERO_POLLUTION",
            "db_written": False,
            "speech_reply": "Ok mapla! Drop panniten, database clean-ah irukku."
        }
