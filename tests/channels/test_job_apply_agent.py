"""Unit and Integration Tests for Autonomous Placement & Job Application Agent."""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from app.agents.placement.job_apply_agent import JobApplyAgent, MUKIL_MASTER_RESUME_URL
from app.tools.agent_brain import AutonomousAgentBrain


def test_job_01_search_jobs():
    """JOB-01: JobApplyAgent generates verified job search URLs across platforms."""
    agent = JobApplyAgent(api_key="mock_key")
    listings = agent.search_jobs(role="AI Engineer", location="Bangalore")
    assert len(listings) >= 4
    platforms = [item["platform"] for item in listings]
    assert any("LinkedIn" in p for p in platforms)
    assert any("Google" in p for p in platforms)
    assert any("Wellfound" in p for p in platforms)


def test_job_02_application_package_generation():
    """JOB-02: Generates customized application package with Mukil's Master Resume."""
    agent = JobApplyAgent(api_key="mock_key")
    pkg = agent.generate_application_package(company_name="Google", job_title="AI Engineer")
    assert "cover_letter" in pkg
    assert "cold_pitch_email" in pkg
    assert "screening_answer_why_hire" in pkg
    assert MUKIL_MASTER_RESUME_URL in pkg["cover_letter"] or MUKIL_MASTER_RESUME_URL in pkg["cold_pitch_email"]


def test_job_03_log_and_pipeline_summary():
    """JOB-03: Logs application and generates formatted pipeline tracker."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = os.path.join(tmp_dir, "test_jobs.json")
        with patch("app.agents.placement.job_apply_agent.APPLICATIONS_FILE", tmp_file):
            agent = JobApplyAgent(api_key="mock_key")
            logged = agent.log_application(company="Swiggy", role="Full Stack Developer")
            assert logged["company"] == "Swiggy"
            assert logged["status"] == "APPLIED"
            assert logged["resume_link"] == MUKIL_MASTER_RESUME_URL

            summary = agent.get_pipeline_summary()
            assert "Swiggy" in summary
            assert "Full Stack Developer" in summary
            assert MUKIL_MASTER_RESUME_URL in summary


def test_job_04_agent_brain_job_tools():
    """JOB-04: Agent brain dispatches search_and_hunt_jobs and create_job_application tools."""
    brain = AutonomousAgentBrain(api_key="mock_key")

    # Test search_and_hunt_jobs
    res, photo = brain.execute_tool("search_and_hunt_jobs", {"role": "AI Engineer", "location": "Remote"})
    assert "Active Job Opportunities Found" in res
    assert "LinkedIn Jobs" in res
    assert MUKIL_MASTER_RESUME_URL in res

    # Test create_job_application
    res_app, _ = brain.execute_tool("create_job_application", {"company": "Zoho", "role": "AI Developer"})
    assert "AUTONOMOUS JOB APPLICATION EXECUTED FOR ZOHO" in res_app
    assert "Application logged in pipeline tracker" in res_app

    # Test batch_apply_jobs
    res_batch, _ = brain.execute_tool("batch_apply_jobs", {"role": "AI Engineer"})
    assert "BATCH APPLICATION EXECUTED ACROSS TOP COMPANIES" in res_batch
    assert "Zoho" in res_batch

    # Test view_job_pipeline
    res_pipe, _ = brain.execute_tool("view_job_pipeline", {})
    assert "JOB APPLICATION PIPELINE" in res_pipe

