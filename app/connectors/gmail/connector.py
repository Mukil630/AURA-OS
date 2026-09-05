"""Google Gmail Connector for AURA-OS Enterprise Architecture."""
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.connectors.gmail.contracts import (
    GmailAccountProfileContract,
    GmailRadarScanResultContract,
    GmailVerificationResultContract,
    PlacementAssessmentContract,
    SendEmailRequest,
)
from app.core.contracts.connector import (
    CapabilityContract,
    ConnectorContract,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorHealthContract,
)
from app.core.enums import AuthType, ConnectorStatus, ConnectorType, RiskTier
from app.core.interfaces.connector import IConnector
from tools.gmail_verifier import GmailVerifier


class GoogleGmailConnector(IConnector):
    """
    Google Gmail Verified Integration Connector.
    Provides 24/7 placement assessment tracking, email verification,
    OAuth / App-password authentication checks, and email dispatching.
    """

    def __init__(self, is_mock: Optional[bool] = None, target_email: str = "mukilarasu55@gmail.com"):
        self._connector_id = "connector_google_gmail"
        self._connector_type = ConnectorType.EMAIL
        self._base_url = "https://gmail.googleapis.com/gmail/v1"
        env_mode = os.getenv("ENVIRONMENT", "local").lower()
        self._is_mock = is_mock if is_mock is not None else (env_mode in ("mock", "test", "local"))
        self._connected = True
        self.verifier = GmailVerifier(target_email=target_email)

        self._capabilities: List[CapabilityContract] = [
            CapabilityContract(
                capability_id="gmail.verify_connection",
                connector_id=self._connector_id,
                name="Verify Gmail Connection",
                description="Perform multi-tier handshake verification (OAuth, IMAP, SMTP).",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["gmail.readonly"],
                timeout_seconds=20,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="gmail.get_profile",
                connector_id=self._connector_id,
                name="Get Gmail Profile",
                description="Retrieve authenticated email address, unread count, and total messages.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["gmail.readonly"],
                timeout_seconds=15,
                rate_limit_per_minute=60,
            ),
            CapabilityContract(
                capability_id="gmail.scan_placement_radar",
                connector_id=self._connector_id,
                name="Scan Placement & Interview Radar",
                description="Scan inbox for coding rounds, interview assessments, and shortlisting notifications.",
                risk_tier=RiskTier.TIER_1_LOW,
                required_scopes=["gmail.readonly"],
                timeout_seconds=30,
                rate_limit_per_minute=30,
            ),
            CapabilityContract(
                capability_id="gmail.send_email",
                connector_id=self._connector_id,
                name="Send Authenticated Email",
                description="Dispatch email to recipients with professional signature.",
                risk_tier=RiskTier.TIER_2_MEDIUM,
                required_scopes=["gmail.send"],
                timeout_seconds=30,
                rate_limit_per_minute=20,
            ),
        ]

    @property
    def connector_id(self) -> str:
        return self._connector_id

    @property
    def connector_type(self) -> ConnectorType:
        return self._connector_type

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_contract(self) -> ConnectorContract:
        return ConnectorContract(
            connector_id=self.connector_id,
            name="Google Gmail Verified Intelligence Connector",
            connector_type=self.connector_type,
            auth_type=AuthType.OAUTH2,
            status=ConnectorStatus.CONNECTED if self._connected else ConnectorStatus.DISCONNECTED,
            base_url=self._base_url,
            supported_capabilities=[c.capability_id for c in self._capabilities],
            required_scopes=["gmail.readonly", "gmail.send", "gmail.modify"],
            health_check_endpoint=f"{self._base_url}/users/me/profile",
            last_health_check=datetime.now(timezone.utc),
            is_mcp=False,
            is_mock=self._is_mock,
        )

    def list_capabilities(self) -> List[CapabilityContract]:
        return list(self._capabilities)

    async def health_check(self) -> ConnectorHealthContract:
        res = self.verifier.run_comprehensive_verification(allow_mock=True)
        is_ok = res.get("is_verified", False)
        return ConnectorHealthContract(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if is_ok else ConnectorStatus.AUTH_REQUIRED,
            latency_ms=res.get("latency_ms", 12.0),
            message=res.get("message", "Gmail Verification Status checked."),
        )

    async def execute_capability(
        self,
        request: ConnectorExecutionRequest,
        credentials: Optional[str] = None,
    ) -> ConnectorExecutionResult:
        start = time.time()
        cap_id = request.capability_id
        params = request.parameters

        # 1. Verify Connection
        if cap_id == "gmail.verify_connection":
            verification = self.verifier.run_comprehensive_verification(allow_mock=True)
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=verification.get("is_verified", False),
                status_code=200 if verification.get("is_verified") else 401,
                data=verification,
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # 2. Get Profile
        elif cap_id == "gmail.get_profile":
            verification = self.verifier.run_comprehensive_verification(allow_mock=True)
            profile = GmailAccountProfileContract(
                email_address=verification.get("email_address", self.verifier.target_email),
                messages_total=verification.get("messages_total", 1420),
                threads_total=verification.get("threads_total", 850),
                unread_messages=verification.get("unread_messages", 7),
                history_id=verification.get("history_id", "hist_aura_9981"),
                auth_method=verification.get("auth_method", "sandbox"),
                is_verified=verification.get("is_verified", True),
                last_verified_at=datetime.now(timezone.utc),
            )
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=profile.model_dump(),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # 3. Scan Placement & Interview Radar
        elif cap_id == "gmail.scan_placement_radar":
            max_results = params.get("max_results", 15)
            scan_res = self.verifier.scan_placement_radar(max_results=max_results)
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=True,
                status_code=200,
                data=scan_res,
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        # 4. Send Email
        elif cap_id == "gmail.send_email":
            to_email = params.get("to_email")
            subject = params.get("subject", "Message from Mukilarasu S")
            body = params.get("body", "")
            is_html = params.get("is_html", False)
            cc = params.get("cc")

            if not to_email:
                return ConnectorExecutionResult(
                    request_id=request.request_id,
                    capability_id=cap_id,
                    success=False,
                    status_code=400,
                    error_message="Missing required parameter 'to_email'.",
                    latency_ms=round((time.time() - start) * 1000, 2),
                )

            send_res = self.verifier.send_email(to_email=to_email, subject=subject, body=body, is_html=is_html, cc=cc)
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=send_res.get("success", False),
                status_code=200 if send_res.get("success") else 500,
                data=send_res,
                error_message=send_res.get("error"),
                latency_ms=round((time.time() - start) * 1000, 2),
            )

        return ConnectorExecutionResult(
            request_id=request.request_id,
            capability_id=cap_id,
            success=False,
            status_code=400,
            error_message=f"Unsupported capability '{cap_id}' in GoogleGmailConnector.",
            latency_ms=round((time.time() - start) * 1000, 2),
        )
