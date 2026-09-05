import asyncio
import pytest
from app.agents.swarm import (
    SwarmOrchestrator,
    WebScoutAgent,
    PlacementHunterAgent,
    SGCExecutiveAgent,
    PCPilotAgent,
    MemoryVaultAgent
)


def test_web_scout_agent_job_scraping():
    agent = WebScoutAgent()
    msg = asyncio.run(agent.process_task(agent._prepare_mock_msg("SCRAPE_JOBS", {"query": "AI Engineer", "limit": 2})))
    assert msg.status == "COMPLETED"
    assert msg.result["count"] >= 1


def test_placement_hunter_agent_resume_tailoring():
    agent = PlacementHunterAgent()
    msg = asyncio.run(agent.process_task(agent._prepare_mock_msg("TAILOR_RESUME", {"company": "Zoho", "role": "AI Engineer"})))
    assert msg.status == "COMPLETED"
    assert msg.result["ats_score"] >= 90
    assert "Zoho" in msg.result["target_company"]


def test_sgc_executive_agent_overdue():
    agent = SGCExecutiveAgent()
    msg = asyncio.run(agent.process_task(agent._prepare_mock_msg("CHECK_OVERDUE", {})))
    assert msg.status == "COMPLETED"
    assert msg.result["debtors_count"] > 0
    assert msg.result["total_overdue_inr"] > 0


def test_memory_vault_distributed_drive_mesh():
    agent = MemoryVaultAgent()
    msg = asyncio.run(agent.process_task(agent._prepare_mock_msg("LIST_ALL_MESH_NODES", {})))
    assert msg.status == "COMPLETED"
    assert msg.result["allocated_pool_gb"] == 250
    assert msg.result["total_nodes"] == 10


def test_swarm_orchestrator_delegation():
    orchestrator = SwarmOrchestrator()
    res = asyncio.run(orchestrator.dispatch("SGCExecutive", "DRAFT_REMINDER", {"party_name": "Rajesh Textiles", "amount": 24500}))
    assert res.status == "COMPLETED"
    assert "Rajesh Textiles" in res.result["summary"]


# Helper method monkey-patched for testing
def _prepare_mock_msg(self, action, payload):
    from app.agents.swarm.base_swarm_agent import SwarmTaskMessage
    return SwarmTaskMessage(task_id="test_001", sender="TestHarness", recipient=self.agent_name, action=action, payload=payload)

WebScoutAgent._prepare_mock_msg = _prepare_mock_msg
PlacementHunterAgent._prepare_mock_msg = _prepare_mock_msg
SGCExecutiveAgent._prepare_mock_msg = _prepare_mock_msg
MemoryVaultAgent._prepare_mock_msg = _prepare_mock_msg
