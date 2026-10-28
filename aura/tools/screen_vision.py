"""
AURA OS Screen Vision Tool
Captures the active screen in RAM and performs visual analysis.
"""
import sys
import io
import os
from typing import Optional

def _attach_display():
    """Attaches thread to physical display station on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            h_input = user32.OpenInputDesktop(0, False, 0x0100)
            if h_input:
                user32.SetThreadDesktop(h_input)
            else:
                h_desk = user32.OpenDesktopW("default", 0, False, 0x0100)
                if h_desk:
                    user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

def inspect_screen(question: str = "Describe what is currently visible on the screen") -> str:
    """
    Captures the user's active desktop screen directly in RAM (zero disk writes)
    and analyzes it to help with pair programming, troubleshooting, or visual verification.
    Args:
        question: Specific visual question or task regarding the screen contents.
    """
    _attach_display()
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
    except Exception as e:
        return f"Screen capture error (Display unavailable or session locked): {str(e)}"
    
    if img is None:
        return "Error: Screen grab returned empty image."
    
    try:
        # Resize to reasonable dimension for fast transmission
        img.thumbnail((1280, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        img_bytes = buffer.getvalue()
        
        # Analyze with Gemini Vision
        from google import genai
        from google.genai import types
        from aura.config import GEMINI_API_KEY
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                f"You are AURA, Mukil's AI partner. Analyze this screen capture and answer: {question}"
            ]
        )
        return response.text.strip()
    except Exception as e:
        return f"Visual Analysis Error: {str(e)}"
