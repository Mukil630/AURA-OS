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
- Core Businesses: Sri Ganapathi Colours (Yarn Dyeing) & Industrial Washing Hub.

INSTRUCTION:
Classify the user's intent into one of these categories:
1. `SCHEDULE_REMINDER`: User wants an alarm, timer, or future follow-up.
2. `SGC_BILLING_QUERY`: User asks about customer invoices, turnover, GST, or overdue debtors.
3. `BUSINESS_PAYABLES`: User asks about upcoming supplier bills, EB commercial electricity bills, or marking an expense paid.
4. `WASHING_HUB_OPS`: User asks about industrial washing machine cycles, bio-polish enzymes, silicon finish, or garment lots.
5. `TASK_MANAGEMENT`: User asks to list tasks, check task status, or cancel a task.
6. `GENERAL_CONVERSATION`: Conversational chat, advice, or technical queries.

Analyze the user's request and respond strictly in valid JSON format:
{
  "intent": "SCHEDULE_REMINDER | SGC_BILLING_QUERY | BUSINESS_PAYABLES | WASHING_HUB_OPS | TASK_MANAGEMENT | GENERAL_CONVERSATION",
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

    def _call_reasoning_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Invokes Gemini (or Groq fallback) with structured JSON prompt."""
        # 1. Try Gemini
        if self.gemini_client:
            models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest"]
            for m in models:
                try:
                    res = self.gemini_client.models.generate_content(
                        model=m,
                        contents=f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\nUSER REQUEST: {user_prompt}",
                        config={"response_mime_type": "application/json"}
                    )
                    text = (res.text or "").strip()
                    if text:
                        return json.loads(text)
                except Exception as e:
                    logger.warning(f"Gemini {m} planning error: {e}. Cascading...")

        # 2. Try Groq Fallback
        if self.groq_client:
            groq_models = ["qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]
            for gm in groq_models:
                try:
                    chat_res = self.groq_client.chat.completions.create(
                        model=gm,
                        messages=[
                            {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.2
                    )
                    raw_json = chat_res.choices[0].message.content
                    if raw_json:
                        return json.loads(raw_json)
                except Exception as ge:
                    logger.warning(f"Groq {gm} fallback planning error: {ge}")

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
        elif any(w in p for w in ["bill", "invoices", "turnover", "gst", "debtor"]):
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
                "intent": "SGC_BILLING_QUERY",
                "task_description": "Query SGC billing database",
                "priority": "NORMAL",
                "reminder_time_expr": None,
                "entities": {"action_verb": "query_billing", "target_month": target_m},
                "conversational_reply": "Checking live SGC billing database now..."
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

        # 1. LLM Planning
        plan = self._call_reasoning_llm(clean_input)
        intent = plan.get("intent", "GENERAL_CONVERSATION")
        priority = plan.get("priority", "NORMAL")

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
                durable_task_manager.update_task_status(
                    task_id, status="COMPLETED",
                    result_summary=f"Scheduled reminder for {rem_res['trigger_time_ist']}",
                    result_data=rem_res
                )
                final_reply = (
                    f"⏰ **DURABLE REMINDER SCHEDULED, BOSS!**\n\n"
                    f"📌 **Task:** {desc}\n"
                    f"🕒 **Trigger Time:** `{rem_res['trigger_time_ist']}`\n"
                    f"🆔 **Task ID:** `{task_id}`\n\n"
                    f"<i>SQLite-la persist aayiduchu. Server restart aanaalum alarm miss aagadhu!</i>"
                )
                speech_reply = f"Done Boss! {rem_res['trigger_time_ist']}-ku reminder schedule panniten!"

            # -------------------------------------------------------------
            # DOMAIN B: SGC BILLING & OPERATIONS
            # -------------------------------------------------------------
            elif intent == "SGC_BILLING_QUERY":
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

                # Extract Customer Name if specified
                customer = entities.get("customer")
                if not customer:
                    for known in ["gaia", "sowbhagiya", "laxmi", "sri ganapathi"]:
                        if known in raw_lower:
                            customer = known
                            break

                # 1. Action: Mark Specific Bill as Paid
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

                # 2. Query Specific Bill Details
                elif bill_no:
                    b_rep = sgc_billing_query.format_bill_download_reply(int(bill_no))
                    b_data = sgc_billing_query.get_bill_by_no(int(bill_no))
                    final_reply = b_rep
                    if b_data:
                        speech_reply = f"Bill #{bill_no} {b_data.get('customer')}-ku ₹{float(b_data.get('netAmount', 0)):,.0f} net amount-la iruku Boss."
                        durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary=f"Bill #{bill_no} details fetched", result_data=b_data)
                    else:
                        speech_reply = f"Bill #{bill_no} database-la kedaikala Boss."
                        durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary=f"Bill #{bill_no} not found")

                # 3. Query Specific Customer Ledger
                elif customer:
                    cust_ledger = sgc_billing_query.format_customer_ledger(customer)
                    final_reply = cust_ledger
                    speech_reply = f"{customer.capitalize()} customer ledger ready Boss!"
                    durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary=f"Customer ledger for {customer}")

                # 4. Query GST / Tax Report
                elif any(w in raw_lower for w in ["tax", "gst", "cgst", "sgst", "gstr"]):
                    target_m = entities.get("target_month")
                    if target_m:
                        final_reply = sgc_billing_query.format_verified_tax_report(target_m)
                    else:
                        final_reply = sgc_billing_query.format_dual_month_tax_report()
                    speech_reply = "SGC 5% GST tax calculation report ready Boss!"
                    durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary="SGC GST Tax report generated")

                # 5. Query Overdue Debtors Recovery Radar
                elif any(w in raw_lower for w in ["overdue", "debtor", "recovery", "who owes"]):
                    try:
                        from tools import sgc_overdue_radar
                        final_reply = sgc_overdue_radar.generate_executive_radar_report()
                    except Exception:
                        final_reply = sgc_billing_query.format_verified_bills_report("all")
                    speech_reply = "SGC overdue recovery radar ready Boss!"
                    durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary="Overdue radar generated")

                # 6. Query Specific Month or Count
                elif entities.get("target_month") or any(m in raw_lower for m in ["september", "sep", "october", "oct", "last month", "this month"]):
                    if "sep" in raw_lower:
                        m_term = "september"
                    elif "oct" in raw_lower:
                        m_term = "october"
                    elif "last month" in raw_lower or "prev" in raw_lower:
                        m_term = "previous"
                    else:
                        m_term = entities.get("target_month") or "current"

                    final_reply = sgc_billing_query.format_verified_bills_report(m_term)
                    m = sgc_billing_query.get_ledger_metrics(m_term)
                    if m.get("success"):
                        p_name = m.get("period_name", m_term.capitalize())
                        p_count = m.get("period_bills_count", 0)
                        p_gross = m.get("total_gross", 0)
                        p_gst = m.get("total_gst", 0)
                        speech_reply = f"Boss, {p_name}-la exactly {p_count} bills potrukom. Total turnover ₹{p_gross:,.0f}, GST ₹{p_gst:,.0f}."
                    else:
                        speech_reply = f"{m_term.capitalize()} month bills breakdown ready Boss!"
                    durable_task_manager.update_task_status(task_id, status="COMPLETED", result_summary=f"Bills for {m_term}: {m.get('period_bills_count', 0)} bills", result_data=m)

                # 7. Default: Ground Truth Full Ledger Overview
                else:
                    m = sgc_billing_query.get_ledger_metrics("all")
                    if m.get("success"):
                        final_reply = (
                            f"📊 **Sri Ganapathi Colours (SGC) - Ground Truth Ledger**\n\n"
                            f"🧾 **Total Verified Bills:** **{m['total_bills_in_db']} Bills**\n"
                            f"💵 **Taxable Turnover:** `₹{m['total_subtotal']:,.2f}`\n"
                            f"🏛️ **Total 5% GST:** `₹{m['total_gst']:,.2f}`\n"
                            f"💰 **Gross Invoiced:** `₹{m['total_gross']:,.2f}`\n"
                            f"⏳ **Pending Collections:** `₹{m['pending_amount']:,.2f}` ({m['pending_bills_count']} bills)\n\n"
                            f"☁️ **Vault Link:** [Google Drive Master Bills](https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9)"
                        )
                        speech_reply = f"Boss, SGC record-la total {m['total_bills_in_db']} bills potrukom. Gross turnover ₹{m['total_gross']:,.0f}."
                        durable_task_manager.update_task_status(
                            task_id, status="COMPLETED",
                            result_summary=f"Fetched SGC ledger: {m['total_bills_in_db']} bills, ₹{m['total_gross']:,.2f} gross",
                            result_data=m
                        )
                    else:
                        durable_task_manager.update_task_status(task_id, status="FAILED", error_message=m.get("error"))
                        final_reply = f"⚠️ SGC Billing data fetch error: {m.get('error')}"
                        speech_reply = "SGC billing database access error Boss."

            # -------------------------------------------------------------
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
