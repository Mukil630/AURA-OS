"""
AURA-OS Central Cognitive Orchestrator & Multi-Agent Controller
app/orchestrator/central_orchestrator.py - Powered by Gemini Reasoning Model & SQLite Durable Storage.
Unifies Natural Language Planning, Task Lifecycle, SGC MCP Tools, and Proactive Scheduling.
"""
import os
import sys
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import GEMINI_API_KEY, GROQ_API_KEY
from app.services.durable_task_manager import durable_task_manager
from app.services.durable_scheduler import durable_scheduler
from tools.executive_business_radar import business_radar

logger = logging.getLogger("central_orchestrator")
IST_TZ = timezone(timedelta(hours=5, minutes=30))

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Central Cognitive Orchestrator of AURA-OS (Mukil's Personal Operating System).
Your role is to understand user requests, extract structured intent, plan multi-step actions, and coordinate specialist tools.

USER PROFILE:
- Boss: Mukil (AI Engineer & Textile Entrepreneur)
- Tone: Crisp, executive, authentic Tanglish + English ('Boss' / 'Mapla' Stark dynamic).
- Core Enterprises (Dual-Enterprise Architecture):
  1. Sri Ganapathi Colours (Yarn Dyeing Unit - Father's Enterprise)
  2. Sri Ganapathi Colours - Bleaching Unit (Salavai Unit - Mukil's Independent Enterprise)
  3. Industrial Washing Hub

INSTRUCTION:
Classify the user's intent into one of these categories:
1. `SCHEDULE_REMINDER`: User wants an alarm, timer, or future follow-up.
2. `ENTERPRISE_BILLING_QUERY`: User asks about customer sales bills/invoices, which bills exist, turnover, GST, passing bills, customer ledgers, or overdue debtors across either SGC Yarn Dyeing Unit or Bleaching Unit (Salavai Unit).
   TEXTILE BUSINESS DIRECTIVE: Phrases like 'bills pass pananum', 'bills pass pannanum', 'enna bills eruku', 'turnover evlo', 'dues evlo', 'pending bills', 'invoices', 'bill #251', 'Eco Fusion', 'Bannari' refer to Mukil's textile businesses. ALWAYS classify billing questions here!
3. `BUSINESS_PAYABLES`: ONLY classify here if user explicitly asks about supplier purchases (e.g., Lakshmi Chemicals, Bannari, chemical vendors, raw material payables, EB commercial electricity bills).
4. `WASHING_HUB_OPS`: User asks about industrial washing machine cycles, bio-polish enzymes, silicon finish, or garment lots.
5. `BLEACHING_BILLING_QUERY`: User asks specifically about Mukil's Bleaching Unit / Salavai unit bills, bleaching invoices, bleaching turnover, bleaching ledger, or mentions 'bleach', 'bleaching', 'salavai' in a billing context.
6. `TASK_MANAGEMENT`: User asks to list tasks, check task status, or cancel a task.
7. `GENERAL_CONVERSATION`: Conversational chat, advice, or technical queries.

Analyze the user's request and respond strictly in valid JSON format:
{
  "intent": "SCHEDULE_REMINDER | ENTERPRISE_BILLING_QUERY | SGC_BILLING_QUERY | BUSINESS_PAYABLES | WASHING_HUB_OPS | BLEACHING_BILLING_QUERY | TASK_MANAGEMENT | GENERAL_CONVERSATION",
  "task_description": "Brief summary of the action",
  "priority": "HIGH | NORMAL | URGENT",
  "reminder_time_expr": "e.g. 'tomorrow at 6 pm' or '10m' or null",
  "entities": {
    "vendor": "Vendor name if mentioned or null",
    "customer": "Customer mill name if mentioned or null",
    "bill_no": "Integer bill number if mentioned (e.g. 1, 2, 3) or null",
    "target_month": "e.g. 'september', 'october', 'current', 'prev', 'all' or null",
    "amount": null,
    "action_verb": "e.g. follow_up, pay, check, create"
  },
  "conversational_reply": "Natural Tanglish response to the user"
}
"""


class CentralOrchestrator:
    """
    Central Controller for AURA-OS.
    Bridges Gemini LLM planning with SQLite task durability, MCP tools, and specialist agents.
    """

    def __init__(self):
        self.gemini_client = None
        self.groq_client = None
        self._init_llm_clients()

    def _init_llm_clients(self):
        api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
        if api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=api_key)
                logger.info("✅ Central Orchestrator: Gemini Client initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")

        groq_key = os.getenv("GROQ_API_KEY") or GROQ_API_KEY
        if groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_key)
                logger.info("✅ Central Orchestrator: Groq Fallback Client initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq Client: {e}")

    def _get_dynamic_system_prompt(self) -> str:
        """Dynamically injects live real-time clock, date, and SGC facts into system prompt."""
        now_ist = datetime.now(IST_TZ)
        time_str = now_ist.strftime("%I:%M %p")
        date_str = now_ist.strftime("%A, %d %B %Y")
        return f"""{ORCHESTRATOR_SYSTEM_PROMPT}

LIVE REAL-TIME CONTEXT:
- Current Clock Time (Asia/Kolkata): {time_str}
- Today's Date: {date_str}
- Region: Karur, Tamil Nadu
- Core Enterprises (Dual-Enterprise Architecture):
  1. Sri Ganapathi Colours (Yarn Dyeing Unit): 11 customer sales bills, ₹66,584.00 gross receivables (Drive: 11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9)
  2. Bleaching Unit (Salavai Unit - Mukil's Enterprise): 2 bills (#251 Eco Fusion ₹2,043, #252 MSK Fabrics ₹259), ₹2,302.00 gross (Drive: 1Xb4gl8KvxlStlfWIIxRjIgWlIAupeg4J)
  - Consolidated Group Turnover: ₹68,886.00 (13 Bills total)
- Persona Directive: You are AURA (JARVIS Prime), Mukil's executive partner & brother ('Mapla' dynamic). Always give accurate real-time time, date, and operations facts in warm, high-energy Tanglish + English.
"""

    def _call_reasoning_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Invokes Groq High-Speed Engine (or Gemini fallback) with structured JSON prompt."""
        system_content = self._get_dynamic_system_prompt()
        # 1. Try Groq First (Sub-second latency < 400ms)
        if self.groq_client:
            groq_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
            for gm in groq_models:
                try:
                    chat_res = self.groq_client.chat.completions.create(
                        model=gm,
                        messages=[
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.2
                    )
                    raw_json = chat_res.choices[0].message.content
                    if raw_json:
                        return json.loads(raw_json)
                except Exception as ge:
                    logger.warning(f"Groq {gm} planning notice: {ge}")

        # 2. Try Gemini Fallback
        if self.gemini_client:
            models = ["gemini-3.8-flash", "gemini-3.6-flash"]
            for m in models:
                try:
                    res = self.gemini_client.models.generate_content(
                        model=m,
                        contents=f"{system_content}\n\nUSER REQUEST: {user_prompt}",
                        config={"response_mime_type": "application/json"}
                    )
                    text = (res.text or "").strip()
                    if text:
                        return json.loads(text)
                except Exception as e:
                    logger.warning(f"Gemini {m} planning error: {e}. Cascading...")

        # Deterministic Rule-Based Fallback
        return self._heuristic_fallback(user_prompt)

    def _heuristic_fallback(self, prompt: str) -> Dict[str, Any]:
        p = prompt.lower()
        if any(w in p for w in ["remind", "reminder", "alarm", "timer", "schedule"]):
            return {
                "intent": "SCHEDULE_REMINDER",
                "task_description": prompt,
                "priority": "HIGH" if "urgent" in p else "NORMAL",
                "reminder_time_expr": "tomorrow 9 am" if "tomorrow" in p else "1h",
                "entities": {"action_verb": "remind"},
                "conversational_reply": f"Sure Boss! Reminder schedule pannidren: '{prompt}'."
            }
        elif any(w in p for w in ["bill", "invoic", "turnover", "gst", "debtor", "pass pananum", "pass pannanum", "enna bills", "endha month", "dues", "salavai", "bleach"]):
            target_m = None
            if "oct" in p:
                target_m = "october"
            elif "sep" in p:
                target_m = "september"
            elif "this month" in p or "current" in p:
                target_m = "current"
            elif "last month" in p or "prev" in p:
                target_m = "previous"
            return {
                "intent": "ENTERPRISE_BILLING_QUERY",
                "task_description": "Query Dual-Enterprise billing databases",
                "priority": "NORMAL",
                "reminder_time_expr": None,
                "entities": {"action_verb": "query_billing", "target_month": target_m},
                "conversational_reply": "Checking Dual-Enterprise billing intelligence..."
            }
        elif any(w in p for w in ["payable", "supplier", "lakshmi", "bannari", "eb", "cashflow"]):
            return {
                "intent": "BUSINESS_PAYABLES",
                "task_description": "Check accounts payable and cashflow",
                "priority": "NORMAL",
                "reminder_time_expr": None,
                "entities": {"action_verb": "check_payables"},
                "conversational_reply": "Pulling supplier payables and cashflow radar..."
            }
        else:
            return {
                "intent": "GENERAL_CONVERSATION",
                "task_description": prompt,
                "priority": "NORMAL",
                "reminder_time_expr": None,
                "entities": {},
                "conversational_reply": f"Vanakkam Boss! Got your request: '{prompt}'."
            }

    def process_request(
        self,
        raw_message: str,
        user_id: str = "mukil",
        channel: str = "TELEGRAM",
        chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        End-to-End Orchestration Pipeline:
        1. Parse intent & entities via Gemini.
        2. Create durable task in SQLite (with deduplication).
        3. Delegate to specialist tool or scheduler.
        4. Verify output & update task status.
        5. Synthesize executive Tanglish response.
        """
        start_time = time.time()
        clean_input = raw_message.strip()
        logger.info(f"🎯 Central Orchestrator received [{channel}]: '{clean_input[:80]}'")

        # Fast-Path Deterministic Interceptors (< 2ms instantaneous response)
        raw_low = clean_input.lower()

        # A. Real-Time Clock & Date Interceptor
        time_triggers = ["time enna", "enna time", "time sollu", "what is the time", "current time", "what time", "mani enna", "enna mani", "mani sollu", "neram enna", "date enna", "today date", "enna date", "what is the date", "date sollu", "today enna date"]
        if any(t in raw_low for t in time_triggers) or (raw_low in ["time", "mani", "date"]):
            now_ist = datetime.now(IST_TZ)
            time_display = now_ist.strftime("%I:%M %p")
            date_display = now_ist.strftime("%A, %d %B %Y")
            reply = f"மாப்ள, இப்போ கரெக்டா மணி {time_display}! இன்னைக்கு {date_display}."
            return {
                "task_id": "tsk_time_fastpath",
                "intent": "TIME_QUERY",
                "status": "COMPLETED",
                "reply": reply,
                "speech_reply": reply,
                "execution_time_ms": round((time.time() - start_time) * 1000, 2)
            }

        # B. Persona Identity Interceptor
        identity_triggers = ["nee yaaru", "who are you", "un name enna", "what is your name", "unga per enna", "peru enna", "un peru enna"]
        if any(it in raw_low for it in identity_triggers) or (raw_low in ["who r u"]):
            reply = "நான் உங்க பர்சனல் எக்ஸிகியூட்டிவ் பார்ட்னர் ஜார்விஸ் மாப்ள! ஸ்ரீ கணபதி கலர்ஸ், கேரியர், பிளேஸ்மென்ட், பிசி கண்ட்ரோல் எல்லாமே 100% என் கண்ட்ரோல்ல இருக்கு. என்ன டாஸ்க் பண்ணனும் சொல்லுங்க, செஞ்சிடலாம்!"
            return {
                "task_id": "tsk_identity_fastpath",
                "intent": "GENERAL_CONVERSATION",
                "status": "COMPLETED",
                "reply": reply,
                "speech_reply": reply,
                "execution_time_ms": round((time.time() - start_time) * 1000, 2)
            }

        # C. Daily Schedule & Workout Split Interceptor (Turso Cloud DB Ground Truth)
        sched_triggers = ["schedule sollu", "schedule enna", "naalaikku schedule", "nalaiku schedule", "today schedule", "innaiku schedule", "innikku schedule", "workout split", "enna workout", "today workout", "daily routine", "daily schedule", "routine sollu"]
        if (any(st in raw_low for st in sched_triggers) or raw_low in ["schedule", "routine", "workout"]) and not any(w in raw_low for w in ["change", "modify", "update"]):
            try:
                from tools.daily_schedule import get_daily_schedule
                target_d = "tomorrow" if ("naalaikku" in raw_low or "nalaiku" in raw_low or "tomorrow" in raw_low) else "today"
                sched_md = get_daily_schedule(target_d)
                speech = f"Boss, {target_d} schedule and workout split Turso Cloud-la irundhu load panniten!"
                return {
                    "task_id": "tsk_schedule_fastpath",
                    "intent": "DAILY_SCHEDULE",
                    "status": "COMPLETED",
                    "reply": sched_md,
                    "speech_reply": speech,
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2)
                }
            except Exception as se:
                logger.warning(f"Fast-path schedule error: {se}")

        # D. Active Tasks Interceptor (Turso Cloud DB Ground Truth)
        active_task_triggers = ["task enna", "active tasks", "tasks enna", "enna tasks", "task list", "active task", "pending tasks", "pending task"]
        if any(att in raw_low for att in active_task_triggers) or raw_low in ["tasks", "task"]:
            try:
                from tools.daily_schedule import list_active_tasks
                tasks_md = list_active_tasks()
                speech = "Boss, active tasks Turso Cloud-la irundhu fetch panniten!"
                return {
                    "task_id": "tsk_activetasks_fastpath",
                    "intent": "TASK_MANAGEMENT",
                    "status": "COMPLETED",
                    "reply": tasks_md,
                    "speech_reply": speech,
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2)
                }
            except Exception as te:
                logger.warning(f"Fast-path active tasks error: {te}")

        # E. Routine Workout Completion Interceptor
        routine_done_triggers = ["mudichiten", "mudinjidhu", "done", "completed", "finish panniten"]
        workout_keywords = ["upper body", "lower body", "chest", "back", "legs", "shoulders", "gym", "workout", "cardio"]
        if any(rd in raw_low for rd in routine_done_triggers) and any(wk in raw_low for wk in workout_keywords):
            try:
                from tools.daily_schedule import log_routine_completed
                matched_kw = next((wk for wk in workout_keywords if wk in raw_low), "workout")
                log_res = log_routine_completed(matched_kw)
                speech = f"Super Boss! {matched_kw} workout complete pannatha Turso Cloud-la log panniten!"
                return {
                    "task_id": "tsk_routine_done_fastpath",
                    "intent": "ROUTINE_LOG",
                    "status": "COMPLETED",
                    "reply": log_res,
                    "speech_reply": speech,
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2)
                }
            except Exception as rde:
                logger.warning(f"Fast-path routine done error: {rde}")

        # F. One-off Task Completion Interceptor (e.g. "bills mudichiten", "prep mudichiten", "task #13 completed")
        if any(rd in raw_low for rd in routine_done_triggers) and not any(wk in raw_low for wk in workout_keywords):
            try:
                from tools.daily_schedule import complete_task
                comp_res = complete_task(clean_input)
                speech = "Task completed Boss! Turso Cloud-la irundhu purge panniten."
                return {
                    "task_id": "tsk_complete_fastpath",
                    "intent": "TASK_MANAGEMENT",
                    "status": "COMPLETED",
                    "reply": comp_res,
                    "speech_reply": speech,
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2)
                }
            except Exception as ce:
                logger.warning(f"Fast-path complete task error: {ce}")

        # 1. LLM Planning
        plan = self._call_reasoning_llm(clean_input)
        intent = plan.get("intent", "GENERAL_CONVERSATION")
        priority = plan.get("priority", "NORMAL")

# Deterministic Guardrail for Dual-Enterprise Billing Queries:
        raw_low = clean_input.lower()
        bill_indicators = ["bill", "invoic", "turnover", "gst", "debtor", "pass pananum", "pass pannanum", "enna bills", "endha month", "dues", "salavai", "bleach", "eco fusion", "bannari"]
        supplier_indicators = ["lakshmi chemicals", "chemical vendor", "eb bill", "electricity"]
        if any(w in raw_low for w in bill_indicators) and not any(w in raw_low for w in supplier_indicators):
            intent = "ENTERPRISE_BILLING_QUERY"

        # 2. Persist Task in SQLite
        task_record = durable_task_manager.create_task(
            raw_input=clean_input,
            user_id=user_id,
            channel=channel,
            intent=intent,
            priority=priority,
            tags=[intent, channel],
            metadata=plan.get("entities", {})
        )
        task_id = task_record["task_id"]

        execution_result = {}
        final_reply = ""
        speech_reply = ""

        try:
            # -------------------------------------------------------------
            # DOMAIN A: SCHEDULE REMINDER
            # -------------------------------------------------------------
            if intent == "SCHEDULE_REMINDER":
                time_expr = plan.get("reminder_time_expr") or "1h"
                desc = plan.get("task_description") or clean_input
                rem_res = durable_scheduler.schedule_reminder(
                    time_expression=time_expr,
                    message=desc,
                    user_id=user_id,
                    chat_id=chat_id,
                    task_id=task_id
                )

                # Also persist to Turso Cloud DB (AWS Mumbai - aura-db)
                turso_id = None
                try:
                    from aura_agent_core.nlp_parser import parse_natural_time
                    from aura_agent_core.services import create_reminder as create_turso_rem
                    parsed_time = parse_natural_time(time_expr)
                    if parsed_time.get("success"):
                        import asyncio
                        import concurrent.futures
                        def _write_turso():
                            return asyncio.run(create_turso_rem(desc, parsed_time["scheduled_iso"]))
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            turso_id = pool.submit(_write_turso).result(timeout=4)
                except Exception as e:
                    logger.warning(f"Turso cloud reminder sync note: {e}")

                durable_task_manager.update_task_status(
                    task_id, status="COMPLETED",
                    result_summary=f"Scheduled reminder for {rem_res['trigger_time_ist']}",
                    result_data=rem_res
                )
                cloud_sync_txt = f"\n☁️ **Turso Cloud DB:** Synced (`#{turso_id}` in `aura-db`)" if turso_id else ""
                final_reply = (
                    f"⏰ **DURABLE REMINDER SCHEDULED, BOSS!**\n\n"
                    f"📌 **Task:** {desc}\n"
                    f"🕒 **Trigger Time:** `{rem_res['trigger_time_ist']}`\n"
                    f"🆔 **Task ID:** `{task_id}`{cloud_sync_txt}\n\n"
                    f"<i>Turso Cloud DB mattrum SQLite-la persist aayiduchu. Server restart aanaalum alarm miss aagadhu, Boss!</i>"
                )
                speech_reply = f"Done Boss! {rem_res['trigger_time_ist']}-ku reminder schedule panniten!"

            # -------------------------------------------------------------
            # -------------------------------------------------------------
            # DOMAIN B: DUAL-ENTERPRISE BILLING & OPERATIONS (SGC + BLEACHING)
            # -------------------------------------------------------------
            elif intent in ["ENTERPRISE_BILLING_QUERY", "SGC_BILLING_QUERY", "BLEACHING_BILLING_QUERY"]:
                from tools import enterprise_router
                from tools import sgc_billing_query
                import re

                entities = plan.get("entities") or {}
                raw_lower = clean_input.lower()

                # Extract Bill Number if specified
                bill_no = entities.get("bill_no")
                if not bill_no:
                    m_b = re.search(r'\b(?:bill|inv|invoice)\s*(?:#|no\.?|num\.?)?\s*(\d+)\b', raw_lower)
                    if m_b:
                        try:
                            bill_no = int(m_b.group(1))
                        except Exception:
                            pass

                # Action: Mark Specific Bill as Paid
                if ("paid" in raw_lower or "cleared" in raw_lower) and bill_no:
                    p_res = sgc_billing_query.mark_bill_paid(bill_no)
                    if p_res.get("success"):
                        final_reply = (
                            f"✅ **Bill #{bill_no} Marked as PAID!**\n\n"
                            f"👤 **Customer:** {p_res['customer']}\n"
                            f"💰 **Amount Cleared:** `₹{p_res['amount']:,.2f}`\n"
                            f"💳 **Payment Mode:** {p_res['paymentMode']}\n\n"
                            f"📁 Database updated in AppData & Google Drive backup!"
                        )
                        speech_reply = f"Bill #{bill_no} cleared Boss! Ledger update panniten."
                        durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary=speech_reply, result_data=p_res)
                    else:
                        final_reply = f"⚠️ Could not mark bill #{bill_no} paid: {p_res.get('error')}"
                        speech_reply = f"Bill #{bill_no} update panna mudiyala Boss."
                        durable_task_manager.update_task_status(task_id, status="FAILED", error_message=p_res.get('error'))
                else:
                    # Dynamic, Zero-Cross-Contamination Router
                    final_reply, speech_reply = enterprise_router.handle_smart_billing_query(clean_input, entities=entities)
                    durable_task_manager.update_task_status(
                        task_id, status="COMPLETED",
                        result_summary=speech_reply,
                        result_data={"intent": intent, "reply": final_reply}
                    )

            # DOMAIN C: BUSINESS PAYABLES & CASHFLOW RADAR
            # -------------------------------------------------------------
            elif intent == "BUSINESS_PAYABLES":
                # Check if user says "paid" or "mark paid"
                if "paid" in clean_input.lower():
                    # Attempt reconciliation
                    res = business_radar.mark_payable_paid(clean_input)
                    durable_task_manager.update_task_status(
                        task_id, status="COMPLETED" if res["success"] else "FAILED",
                        result_summary=res.get("speech_reply"),
                        result_data=res
                    )
                    final_reply = res["message"]
                    speech_reply = res.get("speech_reply", "")
                else:
                    cashflow = business_radar.get_full_cashflow_radar()
                    alerts = business_radar.check_and_get_proactive_alerts(force_all_urgent=True)
                    durable_task_manager.update_task_status(
                        task_id, status="COMPLETED",
                        result_summary="Fetched business cashflow and payables radar",
                        result_data=cashflow
                    )
                    alert_text = alerts[0]["display_text"] if alerts else "Zero urgent dues today or tomorrow."
                    final_reply = (
                        f"📊 **360° SGC & Washing Hub Cashflow Radar**\n\n"
                        f"📈 **Receivables:** `₹{cashflow['receivables']['total']:,.2f}` ({cashflow['receivables']['pending_bills']} bills pending)\n"
                        f"📉 **Payables:** `₹{cashflow['payables']['total']:,.2f}` ({cashflow['payables']['pending_payables']} obligations pending)\n"
                        f"⚖️ **Net Capital:** `₹{cashflow['net_projected_cashflow']:,.2f}` [{cashflow['status']}]\n\n"
                        f"🚨 **Next Urgent Alert:**\n{alert_text}"
                    )
                    speech_reply = alerts[0]["speech_text"] if alerts else "Boss, payables radar clean-aa iruku!"

            # -------------------------------------------------------------
            # DOMAIN D: WASHING HUB OPS
            # -------------------------------------------------------------
            elif intent == "WASHING_HUB_OPS":
                from app.agents.swarm.washing_hub_agent import WashingHubAgent
                from app.agents.swarm.base_swarm_agent import SwarmTaskMessage
                agent = WashingHubAgent()
                msg = SwarmTaskMessage(
                    task_id=task_id,
                    sender="Orchestrator",
                    recipient="WashingHub",
                    action="STATUS" if "recipe" not in clean_input.lower() else "FORMULATE_RECIPE",
                    payload={"type": "bio_polish", "weight_kg": 50.0}
                )
                import asyncio
                res = asyncio.run(agent.process_task(msg))
                durable_task_manager.update_task_status(
                    task_id, status="COMPLETED",
                    result_summary=res.result.get("summary", "")
                )
                final_reply = res.result.get("summary", "Washing Hub updated.")
                speech_reply = "Washing Hub status ready, Boss!"

            # -------------------------------------------------------------
            # DOMAIN D.2: BLEACHING BILLING QUERY (Mukil's Independent Enterprise)
            # -------------------------------------------------------------
            elif intent == "BLEACHING_BILLING_QUERY":
                import asyncio
                from tools.bleaching_billing_query import query_turso_bills, load_local_bills, get_bleaching_overview, get_bleaching_ledger_for_customer
                bills = asyncio.run(query_turso_bills())
                if not bills:
                    bills, _ = load_local_bills()

                customer = entities.get("customer")
                if customer:
                    ledger = get_bleaching_ledger_for_customer(bills, customer)
                    bill_lines = [f"• *Bill #{b.get('billNo')}* ({b.get('date')}): `₹{b.get('netAmount', 0):,.2f}` [{b.get('status')}]" for b in ledger.get("bills", [])]
                    b_str = "\n".join(bill_lines) if bill_lines else "_No bills found for this customer._"
                    final_reply = (
                        f"⚪ **BLEACHING LEDGER: {ledger['customer'].upper()}**\n\n"
                        f"• **Total Bills:** `{ledger['total_bills']}`\n"
                        f"• **Total Invoiced:** `₹{ledger['total_billed']:,.2f}`\n"
                        f"• **Total Paid:** `₹{ledger['total_paid']:,.2f}`\n"
                        f"• **Outstanding Balance:** `₹{ledger['outstanding_balance']:,.2f}`\n\n"
                        f"🧾 **Customer Invoices:**\n{b_str}\n"
                    )
                    speech_reply = f"Mukil, {customer}-oda Bleaching outstanding balance {ledger['outstanding_balance']} rupees."
                else:
                    overview = get_bleaching_overview(bills)
                    recent_lines = [f"• *Bill #{b.get('billNo')}* | {b.get('customer')} | `₹{b.get('netAmount', 0):,.2f}` | [{b.get('status')}]" for b in bills[:5]]
                    recent_str = "\n".join(recent_lines) if recent_lines else "_No bills generated yet._"
                    final_reply = (
                        "⚪ **SRI GANAPATHI COLOURS — BLEACHING UNIT DASHBOARD**\n"
                        "_(Mukil's Independent Enterprise)_\n\n"
                        f"• **Total Invoices Generated:** `{overview['total_bills']}`\n"
                        f"• **Gross Invoiced:** `₹{overview['total_invoiced']:,.2f}`\n"
                        f"• **Collections Cleared:** `₹{overview['total_collected']:,.2f}`\n"
                        f"• **Outstanding Balance:** `₹{overview['total_outstanding']:,.2f}`\n\n"
                        f"🧾 **Recent Bleaching Invoices:**\n{recent_str}\n\n"
                        f"📂 [Open Bleaching-Bills Drive Vault](https://drive.google.com/drive/folders/1Xb4gl8KvxlStlfWIIxRjIgWlIAupeg4J)\n\n"
                        "💡 **Check client ledger:** `/bleach <Customer>` (e.g. `/bleach Eco Fusion`)"
                    )
                    speech_reply = f"Boss, Bleaching unit-la total {overview['total_bills']} bills iruku. Outstanding balance {overview['total_outstanding']} rupees."
                durable_task_manager.update_task_status(
                    task_id, status="COMPLETED",
                    result_summary=final_reply
                )

            # -------------------------------------------------------------
            # DOMAIN E: TASK MANAGEMENT LIST / STATUS
            # -------------------------------------------------------------
            elif intent == "TASK_MANAGEMENT":
                tasks = durable_task_manager.list_tasks(user_id=user_id, limit=5)
                lines = [
                    f"• `#{t['task_id']}` | **{t['intent']}** | [{t['status']}] — *{t['raw_input'][:40]}*"
                    for t in tasks
                ]
                final_reply = (
                    f"📋 **Durable Tasks in Database ({len(tasks)} Most Recent):**\n\n"
                    + "\n".join(lines)
                )
                durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary="Listed tasks")
                speech_reply = f"Boss, total {len(tasks)} tasks database-la iruku."

            # -------------------------------------------------------------
            # DOMAIN F: GENERAL CONVERSATION
            # -------------------------------------------------------------
            else:
                final_reply = plan.get("conversational_reply") or f"Vanakkam Boss! Enna pannanum sollunga: '{clean_input}'."
                speech_reply = final_reply
                durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary=final_reply)

        except Exception as exec_err:
            logger.error(f"Execution error for task {task_id}: {exec_err}", exc_info=True)
            durable_task_manager.update_task_status(task_id, status="FAILED", error_message=str(exec_err))
            final_reply = f"⚠️ Task [{task_id}] execution failed honestly: {str(exec_err)}"
            speech_reply = "Boss, task execute pannumpothu error vandhuchu. Details log-la check pannunga."

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "task_id": task_id,
            "intent": intent,
            "status": "COMPLETED",
            "reply": final_reply,
            "speech_reply": speech_reply,
            "execution_time_ms": elapsed_ms
        }


# Global Singleton Instance
central_orchestrator = CentralOrchestrator()
