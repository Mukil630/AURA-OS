import os
from app.core.config import GEMINI_API_KEY
from app.core.prompt_engine import build_system_prompt
from app.core.memory import session_memory
from app.services.tools import get_pc_vitals, get_sgc_ledger_brief

async def process_user_turn(user_message: str) -> str:
    """Processes Mukil's speech turn and produces crisp conversational reply."""
    text_lower = user_message.lower()

    # Fast-path verbal tool triggers
    if any(k in text_lower for k in ["battery", "vitals", "cpu", "laptop status", "pc status"]):
        vit = get_pc_vitals()
        reply = f"Boss, PC vitals status: {vit}. Ellaame smooth-ah run aagudhu!"
        session_memory.add_turn("user", user_message)
        session_memory.add_turn("assistant", reply)
        return reply

    if any(k in text_lower for k in ["sgc", "billing", "bill status", "overdue", "ledger"]):
        ledger = get_sgc_ledger_brief()
        reply = f"Boss, SGC record updates: {ledger}. Indha details CA-ku forward panlama?"
        session_memory.add_turn("user", user_message)
        session_memory.add_turn("assistant", reply)
        return reply

    # Gemini 3.8 Flash inference
    system_prompt = build_system_prompt()
    conversation_transcript = session_memory.format_history_for_prompt()

    full_prompt = (
        f"{system_prompt}\n\n"
        f"CONVERSATION HISTORY:\n{conversation_transcript}\n\n"
        f"Mukil just said: \"{user_message}\"\n\n"
        f"JARVIS Spoken Response (Crisp, under 30 words, direct answer + intelligent follow-up):"
    )

    if GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=full_prompt
            )
            if response and response.text:
                reply = response.text.strip()
                session_memory.add_turn("user", user_message)
                session_memory.add_turn("assistant", reply)
                return reply
        except Exception as e:
            print(f"[Brain Error] Gemini generation error: {e}")

    # Fallback response
    fallback = "Boss, unga voice reach aachu! System 100% active. Adutha step execute panlama?"
    session_memory.add_turn("user", user_message)
    session_memory.add_turn("assistant", fallback)
    return fallback
