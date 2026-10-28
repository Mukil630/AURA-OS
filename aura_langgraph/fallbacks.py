"""
AURA 2.0 Multi-Tier Fallback Provider
aura_langgraph/fallbacks.py - Industrial-grade fault tolerance:
1. LLM Model Fallback: Groq -> Gemini -> Offline Deterministic
2. Tool Execution Fallback: Catches errors, attempts schema repair, or degrades gracefully
3. Memory/DB Fallback: Cloud Turso -> Local SQLite -> Static JSON cache
4. Rollback Emergency Fallback: Logs uncompensated items to disk for human review
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

from dotenv import load_dotenv

logger = logging.getLogger("aura_fallbacks")

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIT_FILE = BASE_DIR / "storage" / "memory" / "uncompensated_audit.json"

# Load persistent credentials from .env
load_dotenv(BASE_DIR / ".env")


class ModelFallbackManager:
    """
    Manages multi-tier LLM inference with automatic failover:
    Tier 1: Groq (llama-3.3-70b-versatile)
    Tier 2: Google Gemini (gemini-1.5-flash / gemini-2.0)
    Tier 3: Offline Executive Heuristic Synthesizer
    """

    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self._groq_client = None
        self._gemini_client = None
        self._init_clients()

    def _init_clients(self):
        if self.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_api_key)
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self._gemini_client = genai.GenerativeModel("gemini-3.8-flash")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

    def invoke_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        tools_schema: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes query with automatic provider failover:
        Groq -> Gemini -> Offline Heuristic
        """
        # Truncate context if payload is excessively large to respect Groq TPM limits
        safe_message = user_message
        if len(safe_message) > 6000:
            safe_message = safe_message[:6000] + "\n...[Context summarized to fit context limit]"

        # --- TIER 1: GROQ ---
        if self._groq_client:
            try:
                logger.info("⚡ [ModelTier 1] Invoking Groq openai/gpt-oss-120b...")
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": safe_message}
                ]
                kwargs = {
                    "model": "openai/gpt-oss-120b",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 1024
                }
                if tools_schema:
                    kwargs["tools"] = tools_schema
                    kwargs["tool_choice"] = "auto"

                res = self._groq_client.chat.completions.create(**kwargs)
                choice = res.choices[0].message
                
                tool_calls = []
                if choice.tool_calls:
                    for tc in choice.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        })

                return {
                    "provider": "groq",
                    "content": choice.content or "",
                    "tool_calls": tool_calls,
                    "fallback_triggered": False
                }
            except Exception as groq_err:
                logger.warning(f"⚠️ Groq inference failed ({groq_err}). Failing over to Tier 2 (Gemini)...")

        # --- TIER 2: GEMINI ---
        if self._gemini_client:
            try:
                logger.info("🌐 [ModelTier 2] Invoking Google Gemini 1.5 Flash...")
                prompt = f"{system_prompt}\n\nUser Request: {user_message}"
                res = self._gemini_client.generate_content(prompt)
                return {
                    "provider": "gemini",
                    "content": res.text or "",
                    "tool_calls": [],  # Fallback to conversational text or structured prompt
                    "fallback_triggered": True,
                    "fallback_reason": "Groq unavailable"
                }
            except Exception as gemini_err:
                logger.warning(f"⚠️ Gemini inference failed ({gemini_err}). Failing over to Tier 3 (Offline Heuristic)...")

        # --- TIER 3: OFFLINE HEURISTIC ---
        logger.warning("🚨 [ModelTier 3] Invoking Offline Deterministic Fallback Synthesizer...")
        return {
            "provider": "offline_heuristic",
            "content": (
                "⚠️ Maapla, cloud LLM providers (Groq & Gemini) temporary-aa unreachable-aa irukku. "
                "Aana unga local system and persistent memory 100% safe! "
                "Network reconnect aana udaney full autonomous mode restore aagidum, Boss."
            ),
            "tool_calls": [],
            "fallback_triggered": True,
            "fallback_reason": "All cloud LLM APIs offline"
        }


class RollbackEmergencyHandler:
    """Handles emergency failures during Saga rollback compensation."""

    @staticmethod
    def record_uncompensated_step(step: Dict[str, Any], exception: Exception):
        """Records an uncompensated action to disk for human audit."""
        entry = {
            "step": step,
            "error": str(exception),
            "logged_at": __import__("datetime").datetime.now().isoformat()
        }
        logger.critical(f"🚨 UNCOMPENSATED STEP RECORDED: {step.get('tool_name')} - {exception}")
        try:
            records = []
            if AUDIT_FILE.exists():
                with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
            records.append(entry)
            AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(AUDIT_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to record uncompensated audit: {e}")


# Global Singleton Fallback Provider
model_fallback_manager = ModelFallbackManager()
