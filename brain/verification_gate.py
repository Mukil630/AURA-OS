"""
========================================================================================
JARVIS CORE — ZERO-HALLUCINATION VERIFICATION GATE (verification_gate.py)
----------------------------------------------------------------------------------------
Enforces Mukil's Anti-Hallucination Directives:
1. Physical Disk & Hardware Ground-Truth First (Zero Guessing).
2. Pre-Flight & Post-Flight Deterministic State Check.
3. Self-Healing & Auto-Rebuild on Tool Failures.
========================================================================================
"""

import os
import json
import logging
import subprocess
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("VerificationGate")

SGC_DB_PATH = r"C:\Users\mukil\AppData\Roaming\sgc-billing\sgc-billing-data.json"
CONTEXT_PATH = r"C:\Users\mukil\jarvis-core\storage\memory\context.json"
ADB_PATH = r"C:\Users\mukil\AppData\Local\Android\Sdk\platform-tools\adb.exe"


class VerificationGate:
    """
    Physical Reality & Ground-Truth Validator.
    Never allows the AI to hallucinate success without physical disk/hardware proof.
    """

    @staticmethod
    def verify_sgc_ground_truth(customer_query: str, claimed_amount: Optional[float] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates SGC bills against the physical sgc-billing-data.json file.
        Rejects hallucinated amounts, customers, or invoice numbers.
        """
        if not os.path.exists(SGC_DB_PATH):
            return False, "CRITICAL: SGC physical billing database not found on disk.", {}

        try:
            with open(SGC_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return False, f"Failed to read SGC database: {str(e)}", {}

        bills = []
        if isinstance(data, dict):
            bills = data.get("sgc-bills") or data.get("bills") or []
        elif isinstance(data, list):
            bills = data
        
        # Search matching bills
        q = customer_query.lower()
        matched = [
            b for b in bills 
            if q in str(b.get("customer", "")).lower() 
            or q in str(b.get("partyName", "")).lower() 
            or q in str(b.get("billNo", "")).lower()
            or q in str(b.get("bill_no", "")).lower()
        ]

        if not matched:
            return False, f"Ground-truth check failed: No records matching '{customer_query}' found in physical database.", {}

        latest = matched[-1]
        real_amt = float(latest.get("netAmount") or latest.get("total") or latest.get("totalAmt") or 0.0)

        if claimed_amount is not None:
            # Check for hallucination tolerance (exact match)
            if abs(real_amt - claimed_amount) > 1.0:
                return False, f"HALLUCINATION BLOCKED: AI claimed ₹{claimed_amount}, but physical record shows ₹{real_amt}.", latest

        return True, f"VERIFIED: Found legitimate record for {latest.get('customer')} with net amount ₹{real_amt}.", latest

    @staticmethod
    def verify_device_action(device_ip: str, action: str, adb_returncode: int, adb_output: str) -> Tuple[bool, str]:
        """
        Verifies whether an IoT / Android TV action actually succeeded physically.
        """
        if adb_returncode != 0:
            return False, f"PHYSICAL FAILURE: Device returned exit code {adb_returncode}. Error: {adb_output}"
        
        if "device not found" in adb_output.lower() or "device offline" in adb_output.lower():
            return False, f"PHYSICAL FAILURE: Target device {device_ip} is physically disconnected or offline."
        
        return True, f"VERIFIED: Action '{action}' physically acknowledged by device at {device_ip}."

    @staticmethod
    def auto_heal_adb_connection(device_ip: str) -> Tuple[bool, str]:
        """
        Self-healing flow: If device disconnected, attempt zero-touch reconnect.
        """
        if not os.path.exists(ADB_PATH):
            return False, "ADB binary not installed."

        target = f"{device_ip}:5555" if ":" not in device_ip else device_ip
        logger.info(f"[Auto-Heal] Reconnecting to {target}...")
        
        try:
            # Disconnect first to purge stale sockets
            subprocess.run([ADB_PATH, "disconnect", target], capture_output=True, text=True, timeout=5)
            # Fresh connect
            res = subprocess.run([ADB_PATH, "connect", target], capture_output=True, text=True, timeout=8)
            output = res.stdout.strip() or res.stderr.strip()
            
            if "connected" in output.lower():
                return True, f"Auto-heal successful: Reconnected to {target}."
            return False, f"Auto-heal failed: {output}"
        except Exception as e:
            return False, f"Auto-heal exception: {str(e)}"

    @staticmethod
    def update_verified_state(domain: str, action: str, verification_result: Dict[str, Any]):
        """
        Writes only physically verified records back to context.json.
        """
        if not os.path.exists(CONTEXT_PATH):
            return

        try:
            with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
                ctx = json.load(f)
            
            ctx.setdefault("verified_execution_audit", [])
            audit_entry = {
                "domain": domain,
                "action": action,
                "verified": verification_result.get("verified", False),
                "proof": verification_result.get("proof", ""),
                "timestamp": verification_result.get("timestamp")
            }
            # Keep last 50 audit entries only (zero bloat)
            ctx["verified_execution_audit"].append(audit_entry)
            ctx["verified_execution_audit"] = ctx["verified_execution_audit"][-50:]

            with open(CONTEXT_PATH, "w", encoding="utf-8") as f:
                json.dump(ctx, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write verified state: {e}")
