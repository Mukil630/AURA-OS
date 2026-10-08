from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import os

from app.services.brain import process_user_turn
from app.services.tts import synthesize_speech_base64
from app.services.stt import transcribe_audio_groq
from app.core.memory import session_memory

router = APIRouter()

class ChatTurnRequest(BaseModel):
    message: str
    language: Optional[str] = "en-IN"

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "continuous-calling-agent"}

@router.post("/chat")
async def chat_turn(req: ChatTurnRequest):
    user_text = req.message.strip()
    if not user_text:
        return JSONResponse({"reply": "Boss, voice clearly kekala, repeat pannunga?", "audio_b64": ""})

    reply_text = await process_user_turn(user_text)
    audio_b64 = await synthesize_speech_base64(reply_text)

    return JSONResponse({
        "reply": reply_text,
        "audio_b64": audio_b64
    })

@router.post("/reset")
async def reset_call():
    greeting = session_memory.start_session()
    audio_b64 = await synthesize_speech_base64(greeting)
    return JSONResponse({
        "greeting": greeting,
        "audio_b64": audio_b64
    })

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    text = transcribe_audio_groq(audio_bytes, filename=file.filename or "audio.webm")
    return {"text": text or ""}
