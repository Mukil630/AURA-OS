"""Unit tests for Agent Contracts."""
from app.core.contracts.agent import AgentCapabilityContract, AgentContract
from app.core.enums import AgentStatus, AgentType, RiskLevel


def test_agent_contract_creation():
    cap = AgentCapabilityContract(
        capability_id="github.inspect_ci",
        name="Inspect GitHub CI Workflows",
        description="Reads actions and logs from GitHub repository",
        required_tools=["github.list_workflows", "github.get_logs"],
        risk_level=RiskLevel.LOW,
    )
    agent = AgentContract(
        agent_id="github_agent",
        name="GitHub Specialist Agent",
        agent_type=AgentType.CODING,
        description="Specialist in repository code, CI pipelines, and PR management",
        capabilities=[cap],
        allowed_tools=["github.list_workflows", "github.get_logs", "github.apply_fix"],
    )
    assert agent.agent_id == "github_agent"
    assert agent.agent_type == AgentType.CODING
    assert agent.status == AgentStatus.IDLE
    assert len(agent.capabilities) == 1
    assert agent.capabilities[0].capability_id == "github.inspect_ci"
    assert "github.apply_fix" in agent.allowed_tools
