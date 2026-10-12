from datetime import datetime, timedelta
import re
import dateparser
from aura_agent_core.config import IST

TANGLISH_MAP = {
    "naalaiki": "tomorrow",
    "naalaikku": "tomorrow",
    "nalaiku": "tomorrow",
    "nalaikki": "tomorrow",
    "kaalaila": "morning",
    "kalai": "morning",
    "saayandhram": "evening",
    "sayanthram": "evening",
    "saayankalam": "evening",
    "iravu": "night",
    "inikku": "today",
    "innikku": "today",
    "innum": "in",
    "madhiyam": "afternoon",
    "mathiyam": "afternoon",
}


def clean_tanglish(text: str) -> str:
    cleaned = text.lower()
    for tn, en in TANGLISH_MAP.items():
        cleaned = re.sub(rf"\b{tn}\b", en, cleaned)
    # Handle "mani ku" or "manikku" e.g. "6 manikku" -> "6:00"
    cleaned = re.sub(r"(\d{1,2})\s*(?:mani\s*ku|manikku|mani)", r"\1:00", cleaned)
    return cleaned


def parse_natural_time(time_phrase: str) -> dict:
    """
    Parses any natural date, time, or Tanglish phrase into an IST datetime.
    """
    cleaned = clean_tanglish(time_phrase)
    now = datetime.now(IST)

    # 1. Seconds only check (e.g. '5s', '10')
    sec_match = re.match(r"^(\d+)\s*(s|sec|seconds)?$", cleaned)
    if sec_match:
        secs = int(sec_match.group(1))
        target = now + timedelta(seconds=secs)
        return {
            "success": True,
            "target_dt": target,
            "scheduled_iso": target.strftime("%Y-%m-%d %H:%M:%S"),
            "delay_seconds": secs,
            "display": f"{secs}s from now"
        }

    # 2. Check for explicit time (10am, 4:30pm, etc.)
    has_time = bool(re.search(r"(\d{1,2}(:\d{2})?\s*(am|pm)|\b\d{1,2}:\d{2}\b)", cleaned))

    # 3. Parse with dateparser
    settings = {
        'TIMEZONE': 'Asia/Kolkata',
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future',
        'RELATIVE_BASE': now
    }
    parsed = dateparser.parse(cleaned, settings=settings)

    # Fallback: If dateparser fails and explicit time is present alongside 'morning'/'evening'/'night'
    if not parsed and has_time:
        cleaned_fallback = re.sub(r"\b(morning|evening|afternoon|night)\b", "", cleaned)
        cleaned_fallback = re.sub(r"\s+", " ", cleaned_fallback).strip()
        parsed = dateparser.parse(cleaned_fallback, settings=settings)

    if not parsed:
        return {"success": False, "error": f"Could not parse date/time from '{time_phrase}'"}

    # If only date was specified, default to 09:00 AM Executive Morning
    if not has_time and parsed.date() > now.date():
        parsed = parsed.replace(hour=9, minute=0, second=0)

    diff_seconds = (parsed - now).total_seconds()
    scheduled_iso = parsed.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "success": True,
        "target_dt": parsed,
        "scheduled_iso": scheduled_iso,
        "delay_seconds": diff_seconds,
        "display": f"{parsed.strftime('%d-%b-%Y %I:%M %p')} IST"
    }
