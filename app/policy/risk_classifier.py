"""Deterministic Risk Classification Engine for Human-In-The-Loop Autonomy."""
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from app.core.enums import RiskTier


class RiskLevel(str, Enum):
    """Deterministic risk classification taxonomy."""
    R0_READ_HARDWARE = "R0"                     # Read-only PC telemetry (Auto-execute)
    R1_READ_EXTERNAL = "R1"                     # Read-only API queries (Auto-execute)
    R2_SAFE_CREATION = "R2"                     # Non-destructive creates/uploads (Auto-execute)
    R3_MODIFY_REPOSITORY = "R3"                 # Code patches, repo commits (APPROVAL REQUIRED)
    R4_DATA_OVERWRITE_OR_DELETE = "R4"          # Trash/soft-delete, overwrite (APPROVAL REQUIRED)
    R5_SECURITY_OR_CREDENTIAL_CHANGE = "R5"     # Credential rotation, policy change (STRONG CONFIRMATION REQUIRED)
    R6_MACHINE_CONTROL = "R6"                   # Arbitrary shell/process control (HARD REJECTION)


class RiskClassificationEngine:
    """
    Evaluates capabilities against an immutable deterministic risk matrix.
    Risk level belongs to the capability contract and parameters, NOT natural-language wording.
    """

    # Static Risk Mapping Table
    _CAPABILITY_RISK_MAP = {
        # R0 - Hardware Telemetry (Safe Read-Only)
        "pc.get_cpu": (RiskLevel.R0_READ_HARDWARE, RiskTier.TIER_1_LOW, False),
        "pc.get_memory": (RiskLevel.R0_READ_HARDWARE, RiskTier.TIER_1_LOW, False),
        "pc.get_disk": (RiskLevel.R0_READ_HARDWARE, RiskTier.TIER_1_LOW, False),
        "pc.get_network": (RiskLevel.R0_READ_HARDWARE, RiskTier.TIER_1_LOW, False),
        "pc.get_temperature": (RiskLevel.R0_READ_HARDWARE, RiskTier.TIER_1_LOW, False),
        "pc.get_health_summary": (RiskLevel.R0_READ_HARDWARE, RiskTier.TIER_1_LOW, False),

        # R1 - External Read Queries
        "github.list_failed_workflows": (RiskLevel.R1_READ_EXTERNAL, RiskTier.TIER_1_LOW, False),
        "github.get_logs": (RiskLevel.R1_READ_EXTERNAL, RiskTier.TIER_1_LOW, False),
        "drive.list": (RiskLevel.R1_READ_EXTERNAL, RiskTier.TIER_1_LOW, False),
        "drive.get_storage_info": (RiskLevel.R1_READ_EXTERNAL, RiskTier.TIER_1_LOW, False),
        "drive.get_metadata": (RiskLevel.R1_READ_EXTERNAL, RiskTier.TIER_1_LOW, False),
        "drive.download": (RiskLevel.R1_READ_EXTERNAL, RiskTier.TIER_1_LOW, False),

        # R2 - Safe Creation / Ingestion
        "drive.upload": (RiskLevel.R2_SAFE_CREATION, RiskTier.TIER_1_LOW, False),
        "drive.create_folder": (RiskLevel.R2_SAFE_CREATION, RiskTier.TIER_1_LOW, False),
        "drive.sync_vault": (RiskLevel.R2_SAFE_CREATION, RiskTier.TIER_1_LOW, False),
        "telegram.send_message": (RiskLevel.R2_SAFE_CREATION, RiskTier.TIER_1_LOW, False),

        # R3 - Code / Repository Mutation (Human Confirmation Required)
        "coding.apply_fix": (RiskLevel.R3_MODIFY_REPOSITORY, RiskTier.TIER_2_MEDIUM, True),
        "coding.analyze_patch": (RiskLevel.R3_MODIFY_REPOSITORY, RiskTier.TIER_2_MEDIUM, False),
        "github.modify_repository": (RiskLevel.R3_MODIFY_REPOSITORY, RiskTier.TIER_3_HIGH, True),
        "github.create_pr": (RiskLevel.R3_MODIFY_REPOSITORY, RiskTier.TIER_2_MEDIUM, True),

        # R4 - Data Overwrite / Deletion
        "drive.trash_file": (RiskLevel.R4_DATA_OVERWRITE_OR_DELETE, RiskTier.TIER_3_HIGH, True),
        "drive.delete_file": (RiskLevel.R4_DATA_OVERWRITE_OR_DELETE, RiskTier.TIER_3_HIGH, True),

        # R5 - Security & Credential Changes
        "security.rotate_token": (RiskLevel.R5_SECURITY_OR_CREDENTIAL_CHANGE, RiskTier.TIER_4_CRITICAL, True),
        "security.update_policy": (RiskLevel.R5_SECURITY_OR_CREDENTIAL_CHANGE, RiskTier.TIER_4_CRITICAL, True),
        "security.manage_tenant": (RiskLevel.R5_SECURITY_OR_CREDENTIAL_CHANGE, RiskTier.TIER_4_CRITICAL, True),

        # R6 - Prohibited Machine Control
        "pc.shell": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
        "pc.powershell": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
        "pc.command": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
        "pc.exec": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
        "pc.kill_process": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
        "pc.delete_file": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
        "pc.modify_registry": (RiskLevel.R6_MACHINE_CONTROL, RiskTier.TIER_4_CRITICAL, True),
    }

    def classify_capability(
        self,
        capability_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[RiskLevel, RiskTier, bool, str]:
        """
        Classify capability deterministically.
        Returns (risk_level, risk_tier, requires_approval, rationale).
        """
        if capability_id in self._CAPABILITY_RISK_MAP:
            level, tier, req_appr = self._CAPABILITY_RISK_MAP[capability_id]
            rationale = f"Capability '{capability_id}' statically classified as {level.value} ({tier.value})."
            return level, tier, req_appr, rationale

        # Check for forbidden control patterns
        cap_lower = capability_id.lower()
        if any(kw in cap_lower for kw in ["shell", "powershell", "cmd", "exec", "kill", "registry", "shutdown", "reboot"]):
            return (
                RiskLevel.R6_MACHINE_CONTROL,
                RiskTier.TIER_4_CRITICAL,
                True,
                f"Capability '{capability_id}' violates telemetry-only boundary and matches dangerous machine control.",
            )

        # Default fallback for unknown capabilities
        return (
            RiskLevel.R3_MODIFY_REPOSITORY,
            RiskTier.TIER_3_HIGH,
            True,
            f"Unindexed capability '{capability_id}' conservatively assigned high risk requiring approval.",
        )


# Global Singleton Risk Classifier
default_risk_classifier = RiskClassificationEngine()
