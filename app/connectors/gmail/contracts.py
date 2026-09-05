"""Gmail Connector & Verification Data Contracts."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.enums import ConnectorStatus


class GmailAccountProfileContract(BaseModel):
    """Authenticated Gmail user profile contract."""
    email_address: str = Field(..., description="Target Gmail address (e.g. mukilarasu55@gmail.com)")
    messages_total: int = Field(0, description="Total messages in mailbox")
    threads_total: int = Field(0, description="Total conversation threads")
    unread_messages: int = Field(0, description="Unread messages count")
    history_id: Optional[str] = Field(None, description="Mailbox sync history ID")
    auth_method: str = Field("oauth2", description="Authentication mode: oauth2 | app_password | mock")
    is_verified: bool = Field(False, description="Whether the connection and credentials are valid")
    last_verified_at: Optional[datetime] = Field(None, description="Timestamp of last verification test")


class GmailVerificationResultContract(BaseModel):
    """Result of active Gmail verification check."""
    status: ConnectorStatus = Field(..., description="Verification status (connected, auth_required, error)")
    is_verified: bool = Field(..., description="True if Gmail credentials and handshake passed")
    email_address: str = Field(..., description="Verified email address")
    auth_method: str = Field(..., description="Auth method used for verification")
    imap_verified: bool = Field(False, description="IMAP reading verified")
    smtp_verified: bool = Field(False, description="SMTP sending verified")
    api_verified: bool = Field(False, description="Google Gmail REST API verified")
    unread_count: int = Field(0, description="Number of unread emails")
    message: str = Field(..., description="Human-readable verification summary")
    latency_ms: float = Field(0.0, description="Verification response latency in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC verification timestamp")


class PlacementAssessmentContract(BaseModel):
    """Extracted interview invitation or online assessment contract."""
    id: str = Field(..., description="Unique email / assessment ID")
    company: str = Field(..., description="Company name (e.g. Zoho, TCS, Capgemini)")
    role: str = Field(..., description="Job role or assessment title")
    subject: str = Field(..., description="Email subject line")
    sender: str = Field(..., description="Sender email address")
    received_at: str = Field(..., description="Date/Time received")
    assessment_link: Optional[str] = Field(None, description="Online test or video meet link")
    deadline: Optional[str] = Field(None, description="Assessment deadline or interview time")
    priority: str = Field("HIGH", description="Priority level (URGENT, HIGH, MEDIUM, LOW)")
    snippet: str = Field(..., description="Brief snippet of message content")
    action_required: str = Field(..., description="Recommended action for candidate")


class GmailRadarScanResultContract(BaseModel):
    """Result of Placement & Interview Radar scan across Gmail inbox."""
    total_scanned: int = Field(0, description="Total emails analyzed")
    placement_alerts_count: int = Field(0, description="Number of placement/interview emails detected")
    urgent_count: int = Field(0, description="Urgent action required count")
    assessments: List[PlacementAssessmentContract] = Field(default_factory=list, description="List of detected assessments")
    scanned_at: datetime = Field(default_factory=datetime.utcnow, description="Scan execution timestamp")


class SendEmailRequest(BaseModel):
    """Payload to send an authenticated email."""
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content (plaintext or HTML)")
    is_html: bool = Field(False, description="Whether body is HTML")
    cc: Optional[List[str]] = Field(default=None, description="Optional CC recipients")
