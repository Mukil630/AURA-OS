"""
AURA OS Cognitive Loop Engine
Powered by Groq High-Speed Cognitive Engine (Sub-Second Tool Calling)
with Google Gemini Multimodal / Fallback.
Reverse-engineered from Google Antigravity (AGY) core agentic loop:
Thought -> Tool Call -> Feedback Injection -> Self-Healing -> Final Output
"""
import sys
import os
import json
import time
from typing import List, Dict, Any, Generator, Tuple

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from groq import Groq
from aura.config import GEMINI_API_KEY, GROQ_API_KEY, DEFAULT_ENGINE, DEFAULT_MODEL
from aura.kernel.truth_shield import SYSTEM_INSTRUCTION
from aura.tools.registry import registry
from aura.kernel.skill_loader import skill_registry
from aura.kernel.task_manager import task_manager
from aura.memory.brain_store import brain_store

def _safe_prune_messages(messages: List[Dict[str, Any]], keep_count: int = 8) -> List[Dict[str, Any]]:
    """Prunes message history safely so that orphan 'tool' messages without preceding 'tool_calls' assistant are never sent."""
    if len(messages) <= keep_count + 1:
        return messages
    system_msg = messages[0]
    tail = messages[-keep_count:]
    while tail and tail[0].get("role") == "tool":
        tail.pop(0)
    return [system_msg] + tail


class AuraAgent:
    def __init__(self, model: str = "openai/gpt-oss-20b"):
        self.model = model
        self.groq_client = None
        self.gemini_client = None
        
        # 1. Initialize Groq Client (Primary Sub-Second Tool-Calling Engine)
        if GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=GROQ_API_KEY)
            except Exception:
                self.groq_client = None

        # 2. Initialize Gemini Client (Multimodal / Fallback)
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception:
                self.gemini_client = None

        self.session_id = f"sess_{int(time.time())}"
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTION}
        ]
        self.gemini_chat = None
        self._init_gemini_chat()

    def _init_gemini_chat(self):
        """Initializes multi-turn chat session with 1M token context and all registered native tools."""
        if self.gemini_client:
            try:
                from google.genai import types
                native_tools = list(registry._tools.values())
                self.gemini_chat = self.gemini_client.chats.create(
                    model="gemini-3.5-flash-lite",
                    config=types.GenerateContentConfig(
                        tools=native_tools,
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                )
            except Exception:
                self.gemini_chat = None

    def chat_stream(self, user_prompt: str) -> Generator[Tuple[str, str], None, None]:
        """
        Runs the full AGY-style agentic loop with streaming output.
        Enhanced with AGY Monster Superpowers:
        - Reactive Background Task Notifications
        - Progressive Disclosure Skills Injection
        - SQLite FTS5 Persistent Memory Logging & Cross-Session Recall
        """
        # 1. Surface Reactive Background Task Notifications (Zero-Polling)
        pending_notes = task_manager.pop_notifications()
        for note in pending_notes:
            yield ("tool_call", note)

        # 2. Cross-Session Memory Recall (load recent context from persistent brain on first meaningful prompt)
        if len(self.messages) <= 1:
            try:
                recent_turns = brain_store.get_recent_history_across_sessions(limit=6)
                if recent_turns:
                    recall_lines = [f"Recent context from previous sessions:"]
                    for t in recent_turns:
                        role = t.get("role", "user")
                        content = t.get("content", "")[:120]
                        recall_lines.append(f"  - {role}: {content}")
                    recall_text = "\n".join(recall_lines)
                    yield ("tool_call", f"[Brain Recall] Loaded {len(recent_turns)} prior context fragments")
                    self.messages.append({"role": "system", "content": recall_text})
            except Exception:
                pass

        # 3. Dynamic Progressive Disclosure Skills Injection
        matched_skills = skill_registry.match_skills(user_prompt)
        if matched_skills:
            skill_names = [s.name for s in matched_skills]
            yield ("tool_call", f"[AGY Skill Activated: {', '.join(skill_names)}]")
            for s in matched_skills:
                self.messages.append({
                    "role": "system",
                    "content": f"[ACTIVE SKILL: {s.name}]\n{s.content}"
                })

        # 3. Log user input into Persistent Brain (SQLite FTS5)
        brain_store.log_turn(self.session_id, "user", user_prompt)

        # 1. Primary Gemini Engine Mode (Multi-turn chat + all 36 tools + 1 Million Token Window)
        if DEFAULT_ENGINE == "gemini":
            if not self.gemini_chat:
                self._init_gemini_chat()
            if self.gemini_chat:
                try:
                    history_before = len(self.gemini_chat.get_history()) if hasattr(self.gemini_chat, "get_history") else 0
                    response = self.gemini_chat.send_message(user_prompt)
                    
                    if hasattr(self.gemini_chat, "get_history"):
                        for turn in self.gemini_chat.get_history()[history_before:]:
                            for part in getattr(turn, "parts", []):
                                fc = getattr(part, "function_call", None)
                                if fc:
                                    fn_name = getattr(fc, "name", str(fc))
                                    args = getattr(fc, "args", {})
                                    yield ("tool_call", f"[Executing Tool: {fn_name}({str(args)[:60]})]")
                                fr = getattr(part, "function_response", None)
                                if fr:
                                    fr_name = getattr(fr, "name", str(fr))
                                    yield ("tool_result", f"[Result from {fr_name}]")

                    text = response.text or ""
                    brain_store.log_turn(self.session_id, "assistant", text)
                    for char in text:
                        yield ("token", char)
                    return
                except Exception as ge:
                    err_str = str(ge)
                    # Automatic 1-second retry on transient network/DNS drops
                    if "getaddrinfo" in err_str or "Connection" in err_str or "timed out" in err_str:
                        time.sleep(1.2)
                        try:
                            history_before = len(self.gemini_chat.get_history()) if hasattr(self.gemini_chat, "get_history") else 0
                            response = self.gemini_chat.send_message(user_prompt)
                            if hasattr(self.gemini_chat, "get_history"):
                                for turn in self.gemini_chat.get_history()[history_before:]:
                                    for part in getattr(turn, "parts", []):
                                        fc = getattr(part, "function_call", None)
                                        if fc:
                                            fn_name = getattr(fc, "name", str(fc))
                                            args = getattr(fc, "args", {})
                                            yield ("tool_call", f"[Executing Tool: {fn_name}({str(args)[:60]})]")
                                        fr = getattr(part, "function_response", None)
                                        if fr:
                                            fr_name = getattr(fr, "name", str(fr))
                                            yield ("tool_result", f"[Result from {fr_name}]")
                            text = response.text or ""
                            brain_store.log_turn(self.session_id, "assistant", text)
                            for char in text:
                                yield ("token", char)
                            return
                        except Exception:
                            pass
                    yield ("tool_call", f"[Notice: Gemini reconnecting ({err_str[:40]}...), checking Groq engine...]")

        # 2. Groq Engine (High-Speed Sub-Second Execution)
        if self.groq_client:
            self.messages.append({"role": "user", "content": user_prompt})
            
            # Prune conversation history safely to maintain token budget
            self.messages = _safe_prune_messages(self.messages, keep_count=8)
            
            loop_count = 0
            max_loops = 8
            models_to_try = [self.model, "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
            active_model = self.model
            
            while loop_count < max_loops:
                loop_count += 1
                schemas = registry.get_schemas()
                try:
                    response = self.groq_client.chat.completions.create(
                        model=active_model,
                        messages=self.messages,
                        tools=schemas,
                        tool_choice="auto",
                        temperature=0.3
                    )
                except Exception as e:
                    err_msg = str(e)
                    # Graceful notification on transient network or DNS drop
                    if any(term in err_msg.lower() for term in ["connection error", "getaddrinfo", "timed out", "connecterror"]):
                        yield ("error", "Boss, internet/DNS connection-la chinna drop aagirukku. Reconnect aana udane thirumba try pannunga mapla! ⚡")
                        return
                    # If hit 413 token limit, break out and fall through to Gemini!
                    if ("413" in err_msg or "rate_limit_exceeded" in err_msg or "tokens" in err_msg):
                        if self.gemini_client:
                            yield ("tool_call", f"[Notice: Token limit guard active, seamlessly switching to Gemini 3.5 Flash Lite...]")
                            break
                        elif len(models_to_try) > 1:
                            models_to_try.pop(0)
                            active_model = models_to_try[0]
                            self.messages = _safe_prune_messages(self.messages, keep_count=4)
                            continue
                    yield ("error", f"Model Error: {err_msg}")
                    return
                
                msg = response.choices[0].message
                
                if msg.tool_calls:
                    self.messages.append(msg.to_dict())
                    for tool_call in msg.tool_calls:
                        fn_name = tool_call.function.name
                        raw_args = tool_call.function.arguments
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            args = {}
                            
                        arg_preview = str(args)[:60]
                        yield ("tool_call", f"[Executing Tool: {fn_name}({arg_preview})]")
                        result = registry.execute(fn_name, args)
                        
                        # Guard tool result length to strictly protect TPM limit
                        safe_result_str = str(result)
                        if len(safe_result_str) > 3000:
                            safe_result_str = safe_result_str[:3000] + f"\n\n[... Truncated {len(safe_result_str) - 3000} chars to protect token budget ...]"
                        
                        res_preview = safe_result_str[:100].replace('\n', ' ')
                        yield ("tool_result", f"[Result from {fn_name}: {res_preview}...]")
                        
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": safe_result_str
                        })
                    continue

                final_content = msg.content or ""
                self.messages.append({"role": "assistant", "content": final_content})
                # Log assistant turn to Persistent Brain (SQLite FTS5)
                brain_store.log_turn(self.session_id, "assistant", final_content)
                for char in final_content:
                    yield ("token", char)
                break
            return

        # Primary / Fallback: Gemini Client with Full Native Tool Calling (AFC)
        if self.gemini_client:
            try:
                from google.genai import types
                native_tools = list(registry._tools.values())
                yield ("tool_call", f"[Activating Gemini Engine: gemini-3.5-flash-lite with {len(native_tools)} Native Tools]")
                
                response = self.gemini_client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        tools=native_tools,
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                )
                text = response.text or ""
                # Log assistant turn to Persistent Brain (SQLite FTS5)
                brain_store.log_turn(self.session_id, "assistant", text)
                for char in text:
                    yield ("token", char)
                return
            except Exception as e:
                yield ("error", f"Gemini Engine Error: {str(e)}")
                return

        yield ("error", "No active AI engine available. Please check GEMINI_API_KEY or GROQ_API_KEY in .env.")

    def reset(self):
        """Resets the conversation context."""
        self.messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        self._init_gemini_chat()
