import os
import re
import tempfile
import edge_tts

def detect_language_and_voice(text: str) -> str:
    """Detects whether text contains Tamil script or English/Tanglish and picks the best voice."""
    # Check for Tamil Unicode characters (\u0B80 - \u0BFF)
    tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
    if len(tamil_chars) > 3:
        return "ta-IN-ValluvarNeural"
    
    # Default to high-quality Indian English/Tanglish Neural voice
    return "en-IN-PrabhatNeural"

def clean_text_for_speech(text: str) -> str:
    """Removes markdown symbols, URLs, emojis, and code blocks for clean text-to-speech."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', 'Code block output attached.', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Remove markdown bold/italics/bullet markers
    text = re.sub(r'[\*\#\_\[\]\(\)\~\>\-]', '', text)
    # Remove URLs
    text = re.sub(r'http\S+', 'link', text)
    # Remove emojis that can confuse speech synthesis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:750]  # Limit length for punchy voice notes

async def generate_voice_audio(text: str, custom_voice: str = None) -> str:
    """Generates an MP3 voice note file from text with automatic language and voice selection."""
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task completed successfully, Maapla!"

    selected_voice = custom_voice or detect_language_and_voice(clean_text)

    temp_dir = tempfile.gettempdir()
    audio_path = os.path.join(temp_dir, f"jarvis_voice_{os.getpid()}_{abs(hash(clean_text)) % 100000}.mp3")

    # Communicate with Edge Neural TTS
    communicate = edge_tts.Communicate(clean_text, selected_voice)
    await communicate.save(audio_path)
    return audio_path

