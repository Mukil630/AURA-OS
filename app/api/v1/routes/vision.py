"""
AURA-OS Multimodal Vision Engine & Live Camera Stream Route.
app/api/v1/routes/vision.py
Supports live camera inspection, documents, yarn shades, machinery errors, and screens.
"""
import os
import sys
import time
import base64
import io
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import GEMINI_API_KEY
from app.services.durable_task_manager import durable_task_manager

logger = logging.getLogger("AuraVisionEngine")
router = APIRouter(prefix="/vision", tags=["AURA Live Vision & Multimodal Inspection"])

FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest"]

VISION_SYSTEM_INSTRUCTION = """
You are AURA Live Vision, the multimodal visual intelligence module of AURA-OS for Mukil (AI Engineer & Textile Entrepreneur).
You inspect images captured live from mobile cameras, document scans, textile yarn shades, dyeing machinery, and computer screens.

Rules:
1. Tone: Brotherly, sharp, executive Tanglish + English ('Boss' / 'Mapla' Stark dynamic).
2. For Textile / Yarn / Fabric:
   - Identify shade category (e.g. Navy Blue, Fast Red, Olive Green, Sulfur Black).
   - Comment on shade evenness, tone, and suggest dyeing recipe if relevant.
3. For Invoices / Documents:
   - Extract Mill / Company name, invoice number, taxable amount, and GST.
4. For Machines / Factory / Screens:
   - Diagnose error codes, pressure gauges, temperature alerts, or syntax errors.
5. Provide a two-part response:
   - `analysis`: Crisp markdown breakdown.
   - `speech_reply`: 1-2 punchy spoken Tanglish sentences (under 30 words) for Text-To-Speech audio playback.
"""


def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning(f"Could not initialize google.genai: {e}")
        return None


class Base64VisionRequest(BaseModel):
    image_base64: str
    query: Optional[str] = "Describe what you see and highlight any key details."
    channel: Optional[str] = "MOBILE_APP"


@router.post("/analyze")
async def analyze_image_upload(
    file: Optional[UploadFile] = File(None),
    query: Optional[str] = Form("What do you see in this image? Provide key insights."),
    channel: Optional[str] = Form("MOBILE_CAMERA")
) -> Dict[str, Any]:
    """Analyzes an uploaded image (from mobile camera, gallery, or document scan)."""
    if not file:
        raise HTTPException(status_code=400, detail="No image file provided.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file contents.")

    return await _process_image_bytes(contents, query or "Analyze this image.", channel or "MOBILE_CAMERA")


@router.post("/analyze_base64")
async def analyze_image_base64(req: Base64VisionRequest) -> Dict[str, Any]:
    """Analyzes a base64 encoded image frame from live camera stream."""
    try:
        b64_data = req.image_base64
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

    return await _process_image_bytes(img_bytes, req.query or "Analyze this image.", req.channel or "MOBILE_APP")


async def _process_image_bytes(img_bytes: bytes, prompt: str, channel: str) -> Dict[str, Any]:
    start_time = time.time()
    client = _get_gemini_client()
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API Key is not configured on server.")

    try:
        pil_image = Image.open(io.BytesIO(img_bytes))
        # Resize if overly large (e.g. > 1920px) to conserve bandwidth & speed up latency
        w, h = pil_image.size
        if w > 1920 or h > 1920:
            scale = min(1920 / w, 1920 / h)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to parse image data: {e}")

    # Log task into SQLite Durable Task Manager
    task_record = durable_task_manager.create_task(
        raw_input=f"Live Vision Query: {prompt}",
        user_id="mukil",
        channel=channel,
        intent="VISION_INSPECTION",
        priority="NORMAL",
        tags=["VISION", "MULTIMODAL"],
        metadata={"image_size": f"{w}x{h}"}
    )
    task_id = task_record["task_id"]

    full_prompt = f"{VISION_SYSTEM_INSTRUCTION}\n\nUSER PROMPT: {prompt}\n\nPlease format your response as:\n[ANALYSIS]\n(detailed markdown)\n[SPEECH_REPLY]\n(1-2 conversational Tanglish sentences under 30 words for TTS)"

    response_text = ""
    last_err = None
    for model_name in FALLBACK_MODELS:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=[pil_image, full_prompt]
            )
            if res and res.text:
                response_text = res.text.strip()
                break
        except Exception as e:
            logger.warning(f"Vision call failed on {model_name}: {e}. Retrying with next model...")
            last_err = e
            continue

    if not response_text:
        durable_task_manager.update_task_status(task_id, status="FAILED", error_message=str(last_err))
        raise HTTPException(status_code=500, detail=f"Vision model failed: {last_err}")

    # Parse [ANALYSIS] and [SPEECH_REPLY] sections
    analysis = response_text
    speech_reply = ""
    if "[ANALYSIS]" in response_text and "[SPEECH_REPLY]" in response_text:
        parts = response_text.split("[SPEECH_REPLY]")
        analysis = parts[0].replace("[ANALYSIS]", "").strip()
        speech_reply = parts[1].strip()
    elif "[SPEECH_REPLY]" in response_text:
        parts = response_text.split("[SPEECH_REPLY]")
        analysis = parts[0].strip()
        speech_reply = parts[1].strip()
    else:
        # Fallback speech reply: first sentence
        sentences = [s.strip() for s in response_text.split(".") if s.strip()]
        speech_reply = (sentences[0] + ".") if sentences else "Boss, image analyze panniten!"

    # Clean markdown from speech reply
    speech_reply = speech_reply.replace("*", "").replace("#", "").replace("`", "").strip()

    # Update durable task record
    durable_task_manager.update_task_status(
        task_id,
        status="COMPLETED",
        result_summary=speech_reply[:120],
        result_data={"image_dimensions": f"{w}x{h}", "analysis_chars": len(analysis)}
    )

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "status": "success",
        "task_id": task_id,
        "analysis": analysis,
        "speech_reply": speech_reply,
        "latency_ms": elapsed_ms,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
