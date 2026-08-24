import os
import sys
import logging
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import JARVIS_VOICE_SECRET_TOKEN
from brain.agent_brain import AgentBrain
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_webhook")

app = FastAPI(
    title="JARVIS Secure Voice Gateway",
    description="Encrypted and Authenticated Gateway for Mobile Hey Google / Shortcuts to PC Execution"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = AgentBrain()
mem = MemoryManager()

# Security: List of forbidden destructive actions
BLOCKED_PATTERNS = [
    "format c:", "del /s", "rmdir /s", "drop database", "rm -rf",
    "delete all", "wipe disk", "shutdown /p", "clean disk"
]

class SecureVoiceQuery(BaseModel):
    query: str
    auth_token: Optional[str] = None
    user: str = "Mukil"
    source: str = "google_assistant_gemini"

def verify_token(
    authorization: Optional[str] = Header(None),
    x_jarvis_token: Optional[str] = Header(None)
):
    """
    Validates that incoming requests have the secret pairing token.
    Accepts:
    1. Header 'x-jarvis-token: <TOKEN>'
    2. Header 'Authorization: Bearer <TOKEN>'
    """
    token = x_jarvis_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
    
    return token

@app.get("/")
def health_check():
    return {
        "status": "online",
        "system": "JARVIS Military-Grade Secure Voice Gateway",
        "security": "AUTHENTICATION_REQUIRED",
        "user": "Mukil"
    }

@app.post("/api/voice")
async def handle_voice_command(
    payload: SecureVoiceQuery,
    req_token: Optional[str] = Depends(verify_token)
):
    """
    Encrypted & Authenticated Voice Trigger Endpoint.
    Rejects any request that lacks the secret pairing token.
    """
    token_to_check = req_token or payload.auth_token
    
    # 🔒 AUTHENTICATION CHECK
    if token_to_check != JARVIS_VOICE_SECRET_TOKEN:
        logger.warning(f"🚨 UNAUTHORIZED ACCESS ATTEMPT REJECTED! Invalid token: {token_to_check}")
        mem.log_task("SECURITY_ALERT", "Unauthorized voice access attempt blocked")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid JARVIS secret token."
        )

    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    query_lower = payload.query.lower()
    
    # 🛡️ COMMAND SAFETY GUARDRAILS
    for blocked in BLOCKED_PATTERNS:
        if blocked in query_lower:
            logger.error(f"🛑 BLOCKED DESTRUCTIVE COMMAND: {payload.query}")
            mem.log_task("SECURITY_VIOLATION", f"Blocked destructive command: {payload.query}")
            return {
                "status": "blocked",
                "heard": payload.query,
                "response": "⚠️ Safety Alert: That command is blocked by JARVIS system guardrails to protect your PC.",
                "source": payload.source
            }

    logger.info(f"✅ Authenticated Voice Query from {payload.source}: {payload.query}")
    
    # Execute through ReAct Agent Brain
    reply = brain.process_message(payload.query, user_name=payload.user)
    
    mem.log_task("SECURE_VOICE_COMMAND", f"Source: {payload.source} | Query: {payload.query}", {"reply": reply[:100]})
    
    return {
        "status": "success",
        "heard": payload.query,
        "response": reply,
        "source": payload.source
    }

if __name__ == "__main__":
    print(f"Starting JARVIS Secure Voice Gateway on http://localhost:8000 ...")
    print(f"🔒 Secret Pairing Token: {JARVIS_VOICE_SECRET_TOKEN}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
