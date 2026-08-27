"""Unit tests for Core Enums."""
import pytest
from app.core.enums import (
    AgentStatus,
    AgentType,
    ApprovalState,
    AuthType,
    ChannelType,
    ConnectorStatus,
    ConnectorType,
    Environment,
    EventSeverity,
    EventType,
    ExecutionMode,
    IntentCategory,
    MemoryScope,
    MemoryType,
    PermissionAction,
    PriorityLevel,
    RiskLevel,
    RiskTier,
    StepStatus,
    TaskStatus,
    TaskType,
    ToolCategory,
    ToolExecutionMode,
    VerificationMethod,
    VerificationStatus,
    WorkflowStatus,
)


def test_channel_type_values():
    assert ChannelType.VOICE == "voice"
    assert ChannelType.TELEGRAM == "telegram"
    assert ChannelType.WEB == "web"
    assert ChannelType.MOBILE == "mobile"
    assert ChannelType.DESKTOP == "desktop"
    assert ChannelType.API == "api"


def test_risk_tier_classification():
    assert RiskTier.TIER_1_LOW == "tier_1_low"
    assert RiskTier.TIER_2_MEDIUM == "tier_2_medium"
    assert RiskTier.TIER_3_HIGH == "tier_3_high"
    assert RiskTier.TIER_4_CRITICAL == "tier_4_critical"


def test_task_status_lifecycle():
    assert TaskStatus.CREATED == "created"
    assert TaskStatus.PLANNING == "planning"
    assert TaskStatus.RUNNING == "running"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"


def test_specialist_agent_types():
    assert AgentType.MASTER == "master"
    assert AgentType.RESEARCH == "research"
    assert AgentType.CODING == "coding"
    assert AgentType.CLOUD_FILE == "cloud_file"
    assert AgentType.BROWSER == "browser"
    assert AgentType.COMMUNICATION == "communication"
    assert AgentType.PC == "pc"
