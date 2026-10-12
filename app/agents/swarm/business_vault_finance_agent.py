"""Business Vault & Accounts Payable Finance Agent for AURA-OS Swarm.
app/agents/swarm/business_vault_finance_agent.py - 24/7 Outgoing Obligations,
Company Credential Vault, Proactive Voice Alarms, and Google Drive Ledger Sync.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.swarm.base_swarm_agent import BaseSwarmAgent, SwarmTaskMessage
from tools.executive_business_radar import business_radar

logger = logging.getLogger("BusinessVaultFinanceAgent")


class BusinessVaultFinanceAgent(BaseSwarmAgent):
    """
    Autonomous Outgoing Finance, Company Vault, and Proactive Reminders Partner for Mukil.
    Eliminates human forgetfulness by tracking supplier credit, EB bills, and GST filings.
    """

    def __init__(self):
        super().__init__(
            agent_name="BusinessVaultFinance",
            role_description="Company Business Vault manager, Accounts Payable tracker, and proactive due date alarm executive"
        )

    async def process_task(self, message: SwarmTaskMessage) -> SwarmTaskMessage:
        logger.info(f"💳 [BusinessVaultFinance] Processing action: {message.action}")
        action = message.action.upper()
        payload = message.payload or {}

        try:
            # 1. Proactive Alerts Check
            if action in ["CHECK_ALERTS", "GET_PROACTIVE_ALERTS", "PROACTIVE_RADAR"]:
                force_all = payload.get("force_all", False)
                alerts = business_radar.check_and_get_proactive_alerts(force_all_urgent=force_all)
                if alerts:
                    top_alert = alerts[0]
                    summary = top_alert["display_text"]
                    speech = top_alert["speech_text"]
                else:
                    summary = "✅ **Accounts Payable Radar Clear!**\nNo urgent supplier payments or bills due today or tomorrow."
                    speech = "Boss, inniki naalaiki urgent supplier payments edhum illa. Cashflow safe-aa iruku!"

                message.status = "COMPLETED"
                message.result = {
                    "alerts": alerts,
                    "summary": summary,
                    "speech": speech,
                    "count": len(alerts)
                }
                return message

            # 2. Add New Outgoing Supplier Bill
            elif action in ["ADD_PAYABLE", "LOG_SUPPLIER_BILL", "ADD_BILL"]:
                vendor = payload.get("vendor_name") or payload.get("vendor", "")
                amount = float(payload.get("amount", 0.0))
                due_date = payload.get("due_date")
                desc = payload.get("description", "")
                ref = payload.get("invoice_ref")
                cat = payload.get("category")

                if not vendor or amount <= 0:
                    message.status = "FAILED"
                    message.error = "Vendor name and valid amount required."
                    return message

                res = business_radar.add_payable(
                    vendor_name=vendor,
                    amount=amount,
                    due_date_str=due_date,
                    description=desc,
                    invoice_ref=ref,
                    category=cat
                )
                message.status = "COMPLETED"
                message.result = {
                    "payable": res.get("payable"),
                    "summary": res.get("message")
                }
                return message

            # 3. Reconcile Payment / Mark Paid
            elif action in ["MARK_PAID", "RECONCILE_PAYMENT", "PAID"]:
                identifier = payload.get("identifier") or payload.get("vendor") or payload.get("payable_id", "")
                mode = payload.get("payment_mode", "NEFT")
                ref = payload.get("transaction_ref")

                if not identifier:
                    message.status = "FAILED"
                    message.error = "Payable ID or Vendor Name required to reconcile payment."
                    return message

                res = business_radar.mark_payable_paid(
                    identifier=identifier,
                    payment_mode=mode,
                    transaction_ref=ref
                )
                message.status = "COMPLETED" if res.get("success") else "FAILED"
                message.result = {
                    "reconciled": res.get("reconciled_payment"),
                    "summary": res.get("message"),
                    "speech": res.get("speech_reply", "")
                }
                return message

            # 4. 360-Degree Cashflow Radar
            elif action in ["CASHFLOW_RADAR", "GET_CASHFLOW", "BUSINESS_HEALTH"]:
                radar = business_radar.get_full_cashflow_radar()
                rec = radar["receivables"]
                pay = radar["payables"]
                net = radar["net_projected_cashflow"]
                status_emoji = "🟢" if net >= 0 else "🔴"

                summary = (
                    f"📊 **360° SGC & Washing Hub Cashflow Radar**\n\n"
                    f"📈 **Receivables (Customer Mills):** `₹{rec['total']:,.2f}` ({rec['pending_bills']} bills pending collection)\n"
                    f"📉 **Payables (Suppliers / EB / Tax):** `₹{pay['total']:,.2f}` ({pay['pending_payables']} obligations pending payment)\n"
                    f"────────────────────────────────────────────\n"
                    f"{status_emoji} **Net Working Capital:** `₹{net:,.2f}` [{radar['status']}]\n"
                )
                message.status = "COMPLETED"
                message.result = {
                    "radar": radar,
                    "summary": summary
                }
                return message

            # 5. Fallback List Payables
            else:
                payables_data = business_radar.load_payables()
                active = [p for p in payables_data.get("payables", []) if p.get("status") == "PENDING"]
                lines = [
                    f"• **{p['vendor_name']}**: `₹{p['amount']:,.2f}` (Due: `{p['due_date']}`) — *{p.get('description', '')}*"
                    for p in active
                ]
                summary = (
                    f"📋 **Active Accounts Payable ({len(active)} Dues):**\n\n"
                    + ("\n".join(lines) if lines else "Zero pending obligations!")
                )
                message.status = "COMPLETED"
                message.result = {
                    "payables": active,
                    "summary": summary
                }
                return message

        except Exception as e:
            logger.error(f"Error in BusinessVaultFinanceAgent: {e}", exc_info=True)
            message.status = "FAILED"
            message.error = str(e)
            return message
